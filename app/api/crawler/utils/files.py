from pathlib import Path
from .logger import logger

home_dir = Path.home()
OUTPUT_DIR = home_dir / "crawler_results"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f'Folder Created {OUTPUT_DIR}')
