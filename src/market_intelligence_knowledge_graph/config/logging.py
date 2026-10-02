import logging
import os
from dotenv import load_dotenv


class VSCodeColorFormatter(logging.Formatter):
    """로그 라인 전체를 VSCode 터미널 ANSI 컬러 스타일로 채우는 포맷터"""

    # ANSI 이스케이프 코드 매핑
    COLOR_CODES = {
        logging.DEBUG: "\033[32m",  # Green
        logging.INFO: "\033[36m",  # Cyan (VSCode에서 초록색으로 바꾼 INFO)
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[31m",  # Red
    }
    RESET_CODE = "\033[0m"

    def format(self, record):
        color = self.COLOR_CODES.get(record.levelno, "")

        # [수정] 문자열의 맨 시작 부분에 색상 코드를 넣고, 맨 마지막에만 초기화 코드를 붙입니다.
        # 이렇게 하면 해당 라인 전체의 텍스트 색상이 변경됩니다.
        log_fmt = f"{color}%(asctime)s %(levelname)s [%(name)s] %(message)s{self.RESET_CODE}"

        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def setup_logging() -> None:
    """앱 전체 로깅 설정. main.py에서 앱 만들기 전에 1번 호출."""
    load_dotenv()
    level = os.getenv("LOG_LEVEL")
    if level is None:
        raise RuntimeError("환경변수 LOG_LEVEL 이 없습니다")

    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(VSCodeColorFormatter())

    root_logger.addHandler(console_handler)
