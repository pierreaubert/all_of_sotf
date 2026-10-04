// Inspect only the native dialog owned by the release smoke example.
import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

func fail(_ message: String) -> Never {
    fputs("\(message)\n", stderr)
    exit(1)
}

func ownedWindow(pid: Int32) -> CGWindowID? {
    guard let windows = CGWindowListCopyWindowInfo(.optionOnScreenOnly, kCGNullWindowID)
        as? [[String: Any]] else { return nil }
    var matches: [CGWindowID] = []
    for window in windows {
        guard (window[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value == pid,
              (window[kCGWindowLayer as String] as? NSNumber)?.intValue == CGShieldingWindowLevel(),
              let number = window[kCGWindowNumber as String] as? NSNumber,
              let bounds = window[kCGWindowBounds as String] as? [String: Any],
              ((bounds["Width"] as? NSNumber)?.doubleValue ?? 0) > 200,
              ((bounds["Height"] as? NSNumber)?.doubleValue ?? 0) > 100 else { continue }
        matches.append(number.uint32Value)
    }
    return matches.count == 1 ? matches[0] : nil
}

let args = CommandLine.arguments
guard args.count >= 2 else { fail("usage: native_dialog_macos_window prereq|window|stats ...") }
switch args[1] {
case "prereq":
    // These APIs only inspect TCC state. They never request or change grants.
    print("accessibility_preflight=\(AXIsProcessTrusted())")
    print("screen_capture_preflight=\(CGPreflightScreenCaptureAccess())")
case "window":
    guard args.count == 3, let pid = Int32(args[2]) else {
        fail("window requires example PID")
    }
    guard let number = ownedWindow(pid: pid) else {
        if let windows = CGWindowListCopyWindowInfo(.optionOnScreenOnly, kCGNullWindowID)
            as? [[String: Any]] {
            for window in windows where
                (window[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value == pid {
                let number = window[kCGWindowNumber as String] ?? "missing"
                let layer = window[kCGWindowLayer as String] ?? "missing"
                let bounds = window[kCGWindowBounds as String] ?? "missing"
                fputs("owned-window pid=\(pid) id=\(number) layer=\(layer) bounds=\(bounds)\n", stderr)
            }
        }
        fail("expected exactly one visible native panel owned by pid=\(pid)")
    }
    print(number)
case "stats":
    guard args.count == 3,
          let data = try? Data(contentsOf: URL(fileURLWithPath: args[2])),
          let image = NSBitmapImageRep(data: data),
          image.pixelsWide > 200, image.pixelsHigh > 100 else {
        fail("native dialog screenshot is missing or too small")
    }
    var sum = 0.0
    var squares = 0.0
    var samples = 0.0
    for row in 0..<32 {
        for column in 0..<32 {
            let x = column * (image.pixelsWide - 1) / 31
            let y = row * (image.pixelsHigh - 1) / 31
            guard let color = image.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB) else {
                fail("cannot inspect native dialog screenshot pixels")
            }
            let luminance = 0.2126 * color.redComponent
                + 0.7152 * color.greenComponent + 0.0722 * color.blueComponent
            sum += luminance
            squares += luminance * luminance
            samples += 1
        }
    }
    let mean = sum / samples
    let variance = squares / samples - mean * mean
    print(String(format: "width=%d height=%d mean=%.6f variance=%.6f",
                 image.pixelsWide, image.pixelsHigh, mean, variance))
    guard mean > 0.02, mean < 0.98, variance > 0.0005 else {
        fail("native dialog screenshot is blank or unpainted")
    }
default:
    fail("unknown mode: \(args[1])")
}
