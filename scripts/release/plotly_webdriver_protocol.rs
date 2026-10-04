//! Disposable WebDriver and TLS behavior checks for the Plotly compatibility gate.

use std::io::{BufRead, BufReader, Read, Write};
use std::error::Error;
use std::net::{TcpListener, TcpStream};
use std::process::{Child, Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

fn response(stream: &mut TcpStream, status: &str, body: &str) {
    write!(
        stream,
        "HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    )
    .expect("write mock WebDriver response");
}

fn request(stream: &mut TcpStream) -> String {
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .expect("set mock request timeout");
    let mut bytes = Vec::new();
    let mut chunk = [0_u8; 4096];
    let header_end = loop {
        let count = stream.read(&mut chunk).expect("read mock WebDriver request");
        assert!(count > 0, "WebDriver closed before request headers");
        bytes.extend_from_slice(&chunk[..count]);
        if let Some(position) = bytes.windows(4).position(|window| window == b"\r\n\r\n") {
            break position + 4;
        }
    };
    let headers = String::from_utf8_lossy(&bytes[..header_end]);
    let content_length = headers
        .lines()
        .find_map(|line| {
            let (name, value) = line.split_once(':')?;
            name.eq_ignore_ascii_case("content-length")
                .then(|| value.trim().parse::<usize>().expect("content length"))
        })
        .unwrap_or(0);
    while bytes.len() - header_end < content_length {
        let count = stream.read(&mut chunk).expect("read WebDriver request body");
        assert!(count > 0, "WebDriver closed before request body");
        bytes.extend_from_slice(&chunk[..count]);
    }
    String::from_utf8(bytes).expect("WebDriver request is UTF-8")
}

fn mock_webdriver(mode: &'static str) -> (String, thread::JoinHandle<Vec<String>>) {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind private WebDriver mock");
    listener.set_nonblocking(true).expect("set nonblocking mock listener");
    let url = format!("http://{}", listener.local_addr().expect("mock address"));
    let handle = thread::spawn(move || {
        let expected = if mode == "positive" { 4 } else { 1 };
        let deadline = Instant::now() + Duration::from_secs(15);
        let mut requests = Vec::new();
        while requests.len() < expected {
            assert!(Instant::now() < deadline, "WebDriver mock request count timed out");
            let Ok((mut stream, _)) = listener.accept() else {
                thread::sleep(Duration::from_millis(10));
                continue;
            };
            let text = request(&mut stream);
            let first_line = text.lines().next().expect("request line").to_owned();
            requests.push(text);
            if mode == "malformed" {
                response(&mut stream, "200 OK", "{broken json");
            } else if mode == "status_error" {
                response(
                    &mut stream,
                    "500 Internal Server Error",
                    r#"{"value":{"error":"session not created","message":"mock refusal","stacktrace":""}}"#,
                );
            } else if first_line.starts_with("POST /session ") {
                response(
                    &mut stream,
                    "200 OK",
                    r#"{"value":{"sessionId":"private-session","capabilities":{"browserName":"chrome"}}}"#,
                );
            } else if first_line.starts_with("GET /session/private-session/url ") {
                response(&mut stream, "200 OK", r#"{"value":"http://example.test/start"}"#);
            } else {
                response(&mut stream, "200 OK", r#"{"value":null}"#);
            }
        }
        requests
    });
    (url, handle)
}

#[cfg(feature = "native-tls")]
async fn run_protocol_native() {
    for mode in ["positive", "malformed", "status_error"] {
        let (url, server) = mock_webdriver(mode);
        let result = fantoccini::ClientBuilder::native().connect(&url).await;
        if mode == "positive" {
            let client = result.expect("native TLS connector opens valid WebDriver session");
            assert_eq!(
                client.current_url().await.expect("read current URL").as_str(),
                "http://example.test/start"
            );
            client.goto("http://example.test/next").await.expect("navigate");
            client.close().await.expect("close session");
        } else {
            assert!(result.is_err(), "{mode} WebDriver response must fail");
        }
        assert_requests(mode, server.join().expect("mock WebDriver thread"));
    }
}

#[cfg(feature = "rustls-tls")]
async fn run_protocol_rustls() {
    for mode in ["positive", "malformed", "status_error"] {
        let (url, server) = mock_webdriver(mode);
        let result = fantoccini::ClientBuilder::rustls()
            .expect("construct Rustls connector with native roots")
            .connect(&url)
            .await;
        if mode == "positive" {
            let client = result.expect("Rustls connector opens valid WebDriver session");
            assert_eq!(
                client.current_url().await.expect("read current URL").as_str(),
                "http://example.test/start"
            );
            client.goto("http://example.test/next").await.expect("navigate");
            client.close().await.expect("close session");
        } else {
            assert!(result.is_err(), "{mode} WebDriver response must fail");
        }
        assert_requests(mode, server.join().expect("mock WebDriver thread"));
    }
}

fn assert_requests(mode: &str, requests: Vec<String>) {
    assert!(requests[0].starts_with("POST /session "));
    assert!(requests[0].contains("capabilities"));
    if mode == "positive" {
        assert_eq!(requests.len(), 4);
        assert!(requests[1].starts_with("GET /session/private-session/url "));
        assert!(requests[2].starts_with("POST /session/private-session/url "));
        assert!(requests[2].contains("http://example.test/next"));
        assert!(requests[3].starts_with("DELETE /session/private-session "));
    } else {
        assert_eq!(requests.len(), 1);
    }
}

struct PrivateServer(Child);

impl Drop for PrivateServer {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

fn tls_server() -> (PrivateServer, u16) {
    let script = std::env::var("PLOTLY_TLS_SERVER").expect("private TLS server script path");
    let cert = std::env::var("PLOTLY_TLS_CERT").expect("private server certificate path");
    let key = std::env::var("PLOTLY_TLS_KEY").expect("private server key path");
    let mut child = Command::new("python3")
        .args([script, cert, key])
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .expect("start private TLS server");
    let mut port = String::new();
    BufReader::new(child.stdout.take().expect("private server stdout"))
        .read_line(&mut port)
        .expect("read private TLS server port");
    let port = port.trim().parse().expect("private TLS server port number");
    (PrivateServer(child), port)
}

fn tls_assertions(rustls: bool) {
    let (_server, port) = tls_server();
    let ca = std::fs::read(std::env::var("PLOTLY_TLS_CA").expect("private CA path"))
        .expect("read private CA");
    let root = reqwest::Certificate::from_pem(&ca).expect("parse private CA");
    let builder = reqwest::blocking::Client::builder()
        .add_root_certificate(root)
        .timeout(Duration::from_secs(5));
    let builder = if rustls { builder.use_rustls_tls() } else { builder.use_native_tls() };
    let trusted = builder.build().expect("construct client with private CA");
    let url = format!("https://localhost:{port}/status");
    let response = trusted.get(&url).send().expect("private CA and matching hostname accepted");
    assert_eq!(response.status(), reqwest::StatusCode::OK);
    assert!(response.text().expect("status body").contains("ready"));
    let wrong_host = trusted
        .get(format!("https://127.0.0.1:{port}/status"))
        .send()
        .expect_err("private CA must not bypass hostname verification");
    assert_certificate_failure(&wrong_host);
    assert_eq!(trusted.get(&url).send().expect("server remains reachable after hostname rejection").status(), reqwest::StatusCode::OK);
    let untrusted = if rustls {
        reqwest::blocking::Client::builder().use_rustls_tls().timeout(Duration::from_secs(5)).build()
    } else {
        reqwest::blocking::Client::builder().use_native_tls().timeout(Duration::from_secs(5)).build()
    }
    .expect("construct system-roots client");
    let unknown_ca = untrusted.get(&url).send().expect_err("unknown private CA must be rejected");
    assert_certificate_failure(&unknown_ca);
    assert_eq!(trusted.get(url).send().expect("server remains reachable after unknown-CA rejection").status(), reqwest::StatusCode::OK);
}

fn assert_certificate_failure(error: &reqwest::Error) {
    let mut evidence = error.to_string();
    let mut source = error.source();
    while let Some(cause) = source {
        evidence.push_str(&format!("; {cause}"));
        source = cause.source();
    }
    let lower = evidence.to_lowercase();
    assert!(
        ["certificate", "cert verify", "hostname", "name mismatch", "unknown issuer", "unknown ca", "self signed", "not valid for name"]
            .iter().any(|reason| lower.contains(reason)),
        "TLS rejection lacked certificate or hostname evidence: {evidence}"
    );
}

#[cfg(feature = "native-tls")]
#[tokio::test]
async fn webdriver_protocol_native() {
    run_protocol_native().await;
}

#[cfg(feature = "rustls-tls")]
#[tokio::test]
async fn webdriver_protocol_rustls() {
    run_protocol_rustls().await;
}

#[cfg(feature = "native-tls")]
#[test]
fn private_ca_tls_native() {
    tls_assertions(false);
}

#[cfg(feature = "rustls-tls")]
#[test]
fn private_ca_tls_rustls() {
    tls_assertions(true);
}
