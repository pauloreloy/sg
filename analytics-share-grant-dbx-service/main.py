import signal
import sys
from bootstrap import bootstrap_service
from infrastructure.config import settings

def main():
    consumer = bootstrap_service(settings)

    def shutdown_handler(signum, frame):
        consumer.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    consumer.start()


if __name__ == "__main__":
    main()
