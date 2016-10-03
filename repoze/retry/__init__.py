# repoze retry-on-conflict-error behavior
import itertools
import socket
from tempfile import TemporaryFile
import traceback
from io import BytesIO

# Avoid hard dependency on ZODB.
try:
    from ZODB.POSException import ConflictError
except ImportError:
    class ConflictError(Exception):
        pass

# Avoid hard dependency on Zope2.
try:
    from ZPublisher.Publish import Retry as RetryException
except ImportError:
    class RetryException(Exception):
        pass


class Retry:
    def __init__(self, application, tries, retryable=None):
        
        self.application = application
        self.tries = tries

        if retryable is None:
            retryable = (ConflictError, RetryException,)

        if not isinstance(retryable, (list, tuple)):
            retryable = [retryable]

        self.retryable = tuple(retryable)

    def __call__(self, environ, start_response):
        catch_response = []
        written = []
        original_wsgi_input = environ.get('wsgi.input')

        def replace_start_response(status, headers, exc_info=None):
            catch_response[:] = [status, headers, exc_info]
            return written.append

        count = 0
        while 1:
            try:
                app_iter = self.application(environ, replace_start_response)
            except self.retryable as e:
                count += 1
                if count < self.tries:
                    catch_response[:] = []
                    continue
                if catch_response:
                    if catch_response[0] == "500 Internal Server Error":
                        catch_response[0] = "409 Conflict"
                        start_response(*catch_response)
                    else:
                        start_response(*catch_response)
                raise
            else:
                if catch_response:
                    start_response(*catch_response)
                else:
                    if hasattr(app_iter, 'close'):
                        app_iter.close()
                    raise AssertionError('app must call start_response before '
                                         'returning')
                return close_when_done_generator(written, app_iter)

def close_when_done_generator(written, app_iter):
    try:
        for chunk in itertools.chain(written, app_iter):
            yield chunk
    finally:
        if hasattr(app_iter, 'close'):
            app_iter.close()

def make_retry(app, global_conf, **local_conf):
    from pkg_resources import EntryPoint
    tries = int(local_conf.get('tries', 3))
    retryable = local_conf.get('retryable')
    if retryable is not None:
        retryable = [EntryPoint.parse('x=%s' % x).resolve()
                      for x in retryable.split(' ')]
    return Retry(app, tries, retryable=retryable)
