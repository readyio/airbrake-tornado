import logging
import traceback
import os

from tornado import httpclient
from xml.etree.ElementTree import Element, tostring


def _el_with_text(tag, text, **kwargs):
    el = Element(tag, **kwargs)
    el.text = text
    return el


def _traceback_line(filename, line, method):
    return Element("line",
                   dict(file=filename, method=method, number=str(line)))


def _cgi_data_element(req):
    cgi_data = Element("cgi-data")
    environment = {
        'HTTP_METHOD': req.method,
        'BODY': req.body.decode('utf-8') if req.body else u'',
        'URI': req.uri,
        'PATH': req.path,
        'QUERY': req.uri,
        'URI': req.query,
        'HTTP_VERSION': req.version,
        'REMOTE_IP': req.remote_ip,
        'PROTOCOL': req.protocol,
        'FULL_URL': req.full_url(),
        'REQUEST_TIME': str(req.request_time())
    }
    for key, val in req.headers.iteritems():
        environment[key.upper()] = val
    for key,val in environment.iteritems():
        cgi_data.append(_el_with_text("var", val, key=key))
    return cgi_data

def _params_element(req):
    params = Element("params")
    for key, val in req.arguments.iteritems():
        joined = u','.join([v.decode('utf-8') for v in val])
        params.append(_el_with_text("var", joined, key=key))
    return params


def _request_element(request, component=None):
    req = Element("request")
    req.append(_el_with_text("url", request.uri))
    req.append(_cgi_data_element(request))
    req.append(_params_element(request))
    if component is not None:
      req.append(_el_with_text("component", component))
    return req


def _backtrace_element(exc_info):
    backtrace = Element("backtrace")
    for line in traceback.extract_tb(exc_info[2]):
        backtrace.append(_traceback_line(line[0], line[1], line[2]))
    return backtrace


def notify(exc_info, request, name, api_key=None, environment=None, url=None,
    handler=None):

    if api_key is None or environment is None:
        return

    notice = Element("notice", version="2.3")
    notice.append(_el_with_text("api-key", api_key))

    notifier = Element("notifier")
    notifier.append(_el_with_text("name", name))
    notifier.append(_el_with_text("version", "1.00"))

    if url is not None:
        notifier.append(_el_with_text("url", url))

    notice.append(notifier)

    error = Element("error")
    message = ''
    if exc_info[1].message:
        message = exc_info[1].message.strip()
    if not message:
        message = str(exc_info[1]).strip()
    error.append(_el_with_text("message", message))
    error.append(_el_with_text("class", exc_info[1].__class__.__name__))

    error.append(_backtrace_element(exc_info))
    notice.append(error)
    
    if handler is not None:
      component = handler.__class__.__name__
    else:
      component = None
    notice.append(_request_element(request, component=component))

    server_environment = Element("server-environment")
    pwd = os.environ.get('PWD')
    if pwd:
      server_environment.append(_el_with_text("project-root", pwd))
    server_environment.append(_el_with_text("environment-name", environment))
    notice.append(server_environment)

    def handle_request(response):
        if response.error:
            logging.error("Cannot submit exception: %s", response.error)

    httpclient.AsyncHTTPClient().fetch(
        "http://airbrake.io/notifier_api/v2/notices",
        method="POST",
        body=tostring(notice, encoding='UTF-8'),
        callback=handle_request
    )


__all__ = ["notify"]
