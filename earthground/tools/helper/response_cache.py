import hashlib
import json
import logging
import os
import pathlib
import pickle
from typing import Any, Callable, Dict, List

LOG = logging.getLogger("ApiResponseCache")

BASE_CACHE_DIR = pathlib.Path(".cache")


class ApiResponseCache:
    """
    A class for caching DigiKey API responses.

    This class handles the storage and retrieval of DigiKey API responses
    to reduce API calls and improve performance for repeated queries.
    """

    def __init__(self, api_name: str, cache_dir: str = BASE_CACHE_DIR):
        self.api_name = api_name
        self.folder = cache_dir / api_name
        os.makedirs(self.folder, exist_ok=True)

    def _hash(self, *args) -> str:
        """Create a hash from the arguments to use as a cache key."""
        combined = json.dumps(args, sort_keys=True)
        return hashlib.md5(combined.encode()).hexdigest()

    def get_path(self, function_name: str, args: List[str]) -> str:
        """Create a path for caching responses."""
        return self.folder / f"{function_name}_{self._hash(args)}.pkl"

    def fetch_if_not_cached(
        self, function: Callable, args: List[str], kwargs: Dict[str, Any] = {}
    ) -> Any:
        """Fetch response from API if not cached."""
        # Check cache first
        name = function.__name__
        data = self.check(name, args)
        if data:
            return data

        # If not in cache, fetch externally
        LOG.warning(f"Querying {name} for {args} from {self.api_name}")
        response = function(*args, **kwargs)
        self.save(name, args, response)
        return response

    def check(self, function_name: str, args: List[str]) -> Any:
        """Check if response is cached and return it if found."""
        cache_path = self.get_path(function_name, args)
        if os.path.exists(cache_path):
            LOG.info(f"Cached {function_name} response found for {args}")
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        return None

    def save(self, function_name: str, args: List[str], response: Any) -> None:
        """Save response to cache."""
        cache_path = self.get_path(function_name, args)
        with open(cache_path, "wb") as f:
            pickle.dump(response, f)
        LOG.debug(f"Saved {function_name} response to cache for {args}")
