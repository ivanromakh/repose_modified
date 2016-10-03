import unittest

class CEBase:

    def _getConflictError(self):
        from repoze.retry import ConflictError
        return ConflictError

    ConflictError = property(_getConflictError,)

    def _getRetryException(self):
        from repoze.retry import RetryException
        return RetryException

    RetryException = property(_getRetryException,)

_MINIMAL_HEADERS = [('Content-Type', 'text/plain')]

def _faux_start_response(result, headers, exc_info=None):
    pass

class FactoryTests(unittest.TestCase, CEBase):
    _dummy_start_response_result = None
    
    def _dummy_start_response(self, *arg):
        self._dummy_start_response_result = arg
    
    def _getTargetClass(self):
        from repoze.retry import Retry
        return Retry

    def _makeOne(self, *arg, **kw):
        return self._getTargetClass()(*arg, **kw)

    def _makeEnv(self, **kw):
        return {}
        
    def test_conflict_raised_start_response_called(self):
        application = DummyApplication(conflicts=5, call_start_response=True)
        retry = self._makeOne(application, tries=4,
                              retryable=(self.ConflictError,))
        self.assertRaises(self.ConflictError,
                          retry, self._makeEnv(), self._dummy_start_response)
        self.assertEqual(application.called, 4)
        self.assertEqual(self._dummy_start_response_result,
                         ('409 Conflict', _MINIMAL_HEADERS, None))
        
class Retryable(Exception):
    pass

class AnotherRetryable(Exception):
    pass

class DummyApplication(CEBase):
    iter_factory = list

    def __init__(self, conflicts, call_start_response=False,
                 exception=None):
        self.called = 0
        self.conflicts = conflicts
        self.call_start_response = call_start_response
        if exception is None:
            exception = self.ConflictError
        self.exception = exception
        self.wsgi_input = ''

    def __call__(self, environ, start_response):
        if self.call_start_response:
            start_response('500 Internal Server Error', _MINIMAL_HEADERS)
        if self.called < self.conflicts:
            self.called += 1
            raise self.exception
        istream = environ.get('wsgi.input')
        if istream is not None:
            chunks = []
            chunk = istream.read(1024)
            while chunk:
                chunks.append(chunk)
                chunk = istream.read(1024)
            self.wsgi_input = b''.join(chunks)
        self.app_iter = self.iter_factory([b'hello'])
        return self.app_iter
