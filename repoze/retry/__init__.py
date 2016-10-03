import traceback
from io import BytesIO

try:
    from ZODB.POSException import ConflictError
except ImportError:
    class ConflictError(Exception):
        pass

class Retry:
    def __init__(self, application, tries, retryable=ConflictError):
        
        self.application = application
        self.tries = tries
        self.retryable = tuple(retryable)

    def __call__(self, environ, start_response):
        catch_response = []
        original_wsgi_input = environ.get('wsgi.input')

        def replace_start_response(status, headers, exc_info=None):
            catch_response[:] = [status, headers, exc_info]

        count = 0
        while 1:
            try:
                app_iter = self.application(environ, replace_start_response)
            except ConflictError:
                count += 1
                if count < self.tries:
                    catch_response[:] = []
                    continue
                if catch_response:
                    if catch_response[0] == "500 Internal Server Error":
                        catch_response[0] = "409 Conflict"
                    start_response(*catch_response)
                raise
            else:
                start_response(*catch_response)
                if hasattr(app_iter, 'close'):
                    app_iter.close()
                return 

def make_retry(app, global_conf, **local_conf):
    from pkg_resources import EntryPoint
    tries = int(local_conf.get('tries', 3))
    retryable = local_conf.get('retryable')
    if retryable is not None:
        retryable = [EntryPoint.parse('x=%s' % x).resolve()
                      for x in retryable.split(' ')]
    return Retry(app, tries, retryable=retryable)
