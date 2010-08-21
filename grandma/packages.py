# -*- coding: utf-8 -*-
from xmlrpc_urllib2_transport import ProxyTransport
from django.utils.translation import ugettext as _
from zc.buildout import easy_install
import xmlrpclib
import os
from grandma.models import GrandmaSettings
import urllib2
import re

def search_pypi_xmlrpc(query):
    client = xmlrpclib.ServerProxy('http://pypi.python.org/pypi', transport=ProxyTransport())
    return client.search({'name': query})

def search_index(query):
    cms_settings = GrandmaSettings.objects.get_settings()
    if not cms_settings.package_index or cms_settings.package_index == 'http://pypi.python.org/simple/':
        return search_pypi_xmlrpc(query)
    else:
        # Work with /simple/ index
        # http proxy issue
        proxy_handler = urllib2.ProxyHandler()
        opener = urllib2.build_opener(proxy_handler)
        packages = []
        for line in opener.open(cms_settings.package_index).readlines():
            # Example:
            # <a href="/simple/grandma.django-model-url/"/>grandma.django-model-url</a><br />
            match = re.search('>([\W\w]*)<\/a', line)
            package = {}
            if match:
                # get versions ...
                package_name = match.groups()[0]
                url = cms_settings.package_index + '%s/' % package_name
                versions = set()
                for version_line in opener.open(url).readlines():
                    version_match = re.search('>([\W\w]*)<\/a', version_line)
                    if version_match:
                        # 3rd regexp, find version string in link body
                        # *.tar.gz packages
                        targz_version_match = re.search(
                            '%s-([\d\.\w]+).tar.gz' % package_name, version_match.groups()[0])
                        if targz_version_match:
                            versions.add(targz_version_match.groups()[0])
                        # *.zip packages
                        zip_version_match = re.search(
                            '%s-([\d\.\w]+).zip' % package_name, version_match.groups()[0])
                        if zip_version_match:
                            versions.add(zip_version_match.groups()[0])
                        # python eggs
                        egg_version_match = re.search(
                            '%s-([\d\.\w]+).py\d.\d.egg' % package_name, version_match.groups()[0])
                        if egg_version_match:
                            versions.add(egg_version_match.groups()[0])

                package['name'] = package_name
                package['summary'] = _('No description')
                if versions:
                    package['version'] = versions.pop()

                packages.append(package)

        return filter(lambda package: query in package['name'], packages)


def install(modules, path='parts'):
    '''
    Install module in given path
    Module should be dictionary object, returned by xmlrpc server pypi:
    Example:
        {'_pypi_ordering': 16,
         'name': 'django-tools',
         'summary': 'miscellaneous tools for django',
         'version': '0.10.0.git-ce3ec2d',
    }
    Returns WorkingSet object, 
    see
        http://peak.telecommunity.com/DevCenter/PkgResources#workingset-objects
    terminology:
         http://mail.python.org/pipermail/distutils-sig/2005-June/004652.html
    '''

    path = os.path.abspath(path)
    if not os.path.exists(path):
        os.makedirs(path)

    return easy_install.install(['%s==%s' % (module_['name'], module_['version'])
        for module_ in modules], path)

def test():
    print 'Searching module mptt'
    modules = search_index('mptt')
    if modules:
        print 'found %s modules' % len(modules)
    workset = install([modules[0]])
    mptt_distr = workset.by_key['django-mptt']
    print 'Trying to import mptt'
    mptt_distr.activate()
    from mptt.exceptions import InvalidMove
    print 'Successfull!'

if __name__ == '__main__':
    # run with no parameters for basic test case.
    test()
