import os
import logging
import pickle
import yaml


_CACHE_DIR = '.orgcal_cache'


def check_cache_dir() -> None:
    if not os.path.exists(_CACHE_DIR):
        logging.debug(f'Creating cache directory: {_CACHE_DIR}')
        os.makedirs(_CACHE_DIR)


def read_cache_file(filename: str) -> dict | None:
    full_filename = os.path.join(_CACHE_DIR, filename)
    try:
        with open(full_filename, 'rb') as cache_file:
            return pickle.load(cache_file)
    except Exception as e:
        logging.error(e)


def write_cache_file(filename: str, data: dict) -> None:
    with open(os.path.join(_CACHE_DIR, filename), 'wb') as cache_file:
        pickle.dump(data, cache_file)
