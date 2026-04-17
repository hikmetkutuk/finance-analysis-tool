from importlib import import_module
from typing import Any


def load_dependency(module_name: str) -> Any:
    try:
        return import_module(module_name)
    except ModuleNotFoundError as error:
        message = (
            f"'{module_name}' modulu bulunamadi. "
            "Calistirmadan once `pip install yfinance pandas openpyxl` komutunu calistirin."
        )
        raise ModuleNotFoundError(message) from error


pd = load_dependency("pandas")
yf = load_dependency("yfinance")
try:
    yfinance_exceptions = import_module("yfinance.exceptions")
    YFRateLimitError = getattr(yfinance_exceptions, "YFRateLimitError")
except ModuleNotFoundError:
    YFRateLimitError = OSError
except AttributeError:
    YFRateLimitError = OSError

try:
    curl_request_exceptions = import_module("curl_cffi.requests.exceptions")
    NetworkRequestError = getattr(curl_request_exceptions, "RequestException")
except ModuleNotFoundError:
    NetworkRequestError = OSError
