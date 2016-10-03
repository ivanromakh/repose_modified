import unittest

_MINIMAL_HEADERS = [('Content-Type', 'text/plain')]


# ConflictError and RetryExeption
class CEBase:
    
    def _getConflictError(self):
        from repoze.retry import ConflictError
        return ConflictError

    ConflictError = property(_getConflictError,)

    def _getRetryException(self):
        from repoze.retry import RetryException
        return RetryException

    RetryException = property(_getRetryException,)

def _faux_start_response(result, headers, exc_info=None):
    pass

def unwind(result):
    # we need to close the app iter to shut lint up
    result2 = list(result)
    if hasattr(result, 'close'):
        result.close()
    return result2

# Tests
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
    
    def _makeEnvWithErrorsStream(self, **kw):
        try:
            from StringIO import StringIO
        except ImportError: #pragma NO COVER Py3k
            from io import StringIO
        env = self._makeEnv(**kw)
        env['wsgi.errors'] = StringIO()
        return env
        
    def test_retry_500_server(self):
        application = DummyApplication(conflicts=5, call_start_response=True)
        retry = self._makeOne(application, tries=3, retryable=(self.ConflictError,))
        self.assertRaises(self.ConflictError,
                          retry, self._makeEnv(), self._dummy_start_response)
        self.assertEqual(application.called, 3)
        self.assertEqual(self._dummy_start_response_result,
                         ('409 Conflict', _MINIMAL_HEADERS, None))
        
    def test_200_OK_called(self):
        application = DummyApplication(conflicts=0, call_start_response=True, status = "200 OK")
        retry = self._makeOne(application, tries=3, retryable=(self.ConflictError,))
        retry(self._makeEnv(), self._dummy_start_response)
        self.assertEqual(application.called, 0)
        self.assertEqual(self._dummy_start_response_result,
                         ('200 OK', _MINIMAL_HEADERS, None))
    
    
# Test server 
class DummyApplication(CEBase):
    iter_factory = list

    def __init__(self, conflicts, call_start_response=False, exception=None, status = "500 Internal Server Error"):
        self.called = 0
        self.conflicts = conflicts
        self.call_start_response = call_start_response
        self.status = status
        if exception is None:
            exception = self.ConflictError
        self.exception = exception
        self.wsgi_input = ''

    def __call__(self, environ, start_response):
        if self.call_start_response:
            start_response(self.status, _MINIMAL_HEADERS)
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
