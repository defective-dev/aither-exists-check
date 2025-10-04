import logging
import os
from AppConfig import AppConfig


# Just to same line the logs while logging to file also
class NoNewlineStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            if record.levelno == logging.INFO and (msg.endswith("... ") or msg.endswith(" ")):
                stream.write(msg)
            else:
                stream.write(msg + "\n")
            self.flush()
        except Exception:
            self.handleError(record)

class CustomFileHandlerNewLines(logging.FileHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            if record.levelno == logging.INFO and (msg.endswith("... ") or msg.endswith(" ")):
                stream.write(msg)
            else:
                parts = msg.split(" - ", 2)
                if len(parts) == 2:  # If there's only one delimiter, it means the second one doesn't exist
                    msg = parts[1]
                stream.write(msg + "\n")
            self.flush()
        except Exception:
            self.handleError(record)

def setup_logging(app_configs: AppConfig):
    # Setup logging
    logger = logging.getLogger("customLogger")
    logger.setLevel(logging.INFO)

    # Console handler with a simpler format
    console_handler = NoNewlineStreamHandler()
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with detailed format
    output_path = app_configs.log_files.get("output_path")
    if output_path:
        script_log = os.path.join(os.path.expanduser(output_path), app_configs.log_files["script_log"])
    else:
        script_log = os.path.join(os.path.expanduser(app_configs.log_files["script_log"]))
    file_handler = CustomFileHandlerNewLines(str(script_log))
    file_formatter = logging.Formatter("%(message)s")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
