import sys
import logging
from vs_opc import get_status

logger = logging.getLogger(__name__)


def main():
    logger.info("vs_opc package status: %s", get_status())


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
