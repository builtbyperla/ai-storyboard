from time import time

def get_current_timestamp() -> int:
    '''Get the current timestamp in milliseconds.'''
    return int(time() * 1000)  # milliseconds

def get_reference_timestamp(window_size_ms: int):
    return get_current_timestamp() - window_size_ms
