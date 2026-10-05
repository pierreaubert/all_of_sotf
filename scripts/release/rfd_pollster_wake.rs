// Rust guideline compliant 2026-02-21

#[cfg(test)]
mod tests {
    use std::future::poll_fn;
    use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
    use std::sync::{mpsc, Arc};
    use std::task::{Poll, Waker};
    use std::time::Duration;

    #[test]
    fn cross_thread_wake_resumes_pending_future() {
        let (sender, receiver) = mpsc::sync_channel::<Waker>(1);
        let ready = Arc::new(AtomicBool::new(false));
        let polls = Arc::new(AtomicUsize::new(0));
        let worker_ready = Arc::clone(&ready);
        let worker = std::thread::spawn(move || {
            let waker = receiver
                .recv_timeout(Duration::from_secs(5))
                .expect("first pending poll must publish a waker");
            worker_ready.store(true, Ordering::Release);
            waker.wake();
        });
        let mut sender = Some(sender);
        let actual = pollster::block_on(poll_fn(|context| {
            polls.fetch_add(1, Ordering::Relaxed);
            if ready.load(Ordering::Acquire) {
                Poll::Ready(73)
            } else {
                if let Some(sender) = sender.take() {
                    sender
                        .send(context.waker().clone())
                        .expect("worker receives the pending future's waker");
                }
                Poll::Pending
            }
        }));
        worker.join().expect("wake worker finishes");
        assert_eq!(actual, 73);
        assert!(polls.load(Ordering::Relaxed) >= 2);
    }
}
