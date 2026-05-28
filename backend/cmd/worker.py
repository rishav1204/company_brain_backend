import time

from app.services.worker_service import run_queue_worker_batch


def main() -> None:
    while True:
        run_queue_worker_batch(iterations=50)
        time.sleep(1)


if __name__ == "__main__":
    main()
