from collections import Counter
'''
Since UUIDs use too many tokens, this app instead uses a session number
combined with an in-memory counter (per object type). The session number is
read and incremented from the sessions table in the DB at every startup.

This is safe as long as we are using a single event loop and not yielding
within the logic seen here. The method set_session must be called at startup
after the database has been initialized.
'''
class UniqueIDManager():
    def __init__(self):
        self._session = 0
        self._counters = Counter()

    def set_session(self, session_id: int):
        self._session = session_id

    def _get_id(self, key) -> str:
        current = self._counters[key]
        self._counters[key] += 1
        return f'{self._session}-{current}'

    def get_message_id(self) -> str:
        unique_id = self._get_id('messages')
        return f'msg_{unique_id}'

    def get_image_request_id(self) -> str:
        unique_id = self._get_id('images')
        return f'req_{unique_id}'

    def get_recall_id(self) -> str:
        unique_id = self._get_id('recall')
        return f'memory_{unique_id}'

id_manager = UniqueIDManager()