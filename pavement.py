#########################################################################
#
# Copyright (C) 2012 OpenPlans
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

import os
import re
import shutil
import sys
import time
import urllib
import urllib2
import zipfile
import glob
import fileinput
from setuptools.command import easy_install

from paver.easy import task, options, cmdopts, needs
from paver.easy import path, sh, info, call_task
from paver.easy import BuildFailure

try:
    from geonode.settings import GEONODE_APPS
except:
    #probably trying to run install_win_deps.
    pass

try:
    from paver.path import pushd
except ImportError:
    from paver.easy import pushd

assert sys.version_info >= (2, 6), \
    SystemError("GeoNode Build requires python 2.6 or better")


def grab(src, dest, name):
    download = True
    if not dest.exists():
        print 'Downloading %s' % name
    elif not zipfile.is_zipfile(dest):
        print 'Downloading %s (corrupt file)' % name
    else:
        download = False
    if download:
        urllib.urlretrieve(str(src), str(dest))

GEOSERVER_URL = "http://build.geonode.org/geoserver/latest/geoserver.war"
DATA_DIR_URL = "http://build.geonode.org/geoserver/latest/data.zip"
JETTY_RUNNER_URL = "http://repo2.maven.org/maven2/org/mortbay/jetty/jetty-runner/8.1.8.v20121106/jetty-runner-8.1.8.v20121106.jar"


@task
def setup_geoserver(options):
    """Prepare a testing instance of GeoServer."""
    download_dir = path('downloaded')
    if not download_dir.exists():
        download_dir.makedirs()

    geoserver_dir = path('geoserver')

    geoserver_bin = download_dir / os.path.basename(GEOSERVER_URL)
    jetty_runner = download_dir / os.path.basename(JETTY_RUNNER_URL)

    grab(GEOSERVER_URL, geoserver_bin, "geoserver binary")
    grab(JETTY_RUNNER_URL, jetty_runner, "jetty runner")

    if not geoserver_dir.exists():
        geoserver_dir.makedirs()

        webapp_dir = geoserver_dir / 'geoserver'
        if not webapp_dir:
            webapp_dir.makedirs()

        print 'extracting geoserver'
        z = zipfile.ZipFile(geoserver_bin, "r")
        z.extractall(webapp_dir)

    _install_data_dir()


def _install_data_dir():
    target_data_dir = path('geoserver/data')
    if target_data_dir.exists():
        target_data_dir.rmtree()

    original_data_dir = path('geoserver/geoserver/data')
    justcopy(original_data_dir, target_data_dir)

    config = path('geoserver/data/security/auth/geonodeAuthProvider/config.xml')
    with open(config) as f:
        xml = f.read()
        m = re.search('baseUrl>([^<]+)', xml)
        xml = xml[:m.start(1)] + "http://localhost:8000/" + xml[m.end(1):]
        with open(config, 'w') as f:
            f.write(xml)


@task
def static(options):
    with pushd('geonode/static'):
        sh('make')


@task
@needs([
    'setup_geoserver',
])
def setup(options):
    """Get dependencies and prepare a GeoNode development environment."""

    info(('GeoNode development environment successfully set up.'
          'If you have not set up an administrative account,'
          ' please do so now. Use "paver start" to start up the server.'))


def grab_winfiles(url, dest, packagename):
    #~gohlke needs a user agent that is not python
    # Add your headers
    headers = {'User-Agent': 'Mozilla 5.10'}
    request = urllib2.Request(url, None, headers)
    response = urllib2.urlopen(request)
    with open(dest, 'wb') as writefile:
        writefile.write(response.read())


@task
def win_install_deps(options):
    """
    Install all Windows Binary automatically
    """
    download_dir = path('downloaded').abspath()
    if not download_dir.exists():
        download_dir.makedirs()
    win_packages = {
        "PIL": "https://pypi.python.org/packages/2.7/P/Pillow/Pillow-2.5.1.win32-py2.7.exe",
        "Py2exe": "http://superb-dca2.dl.sourceforge.net/project/py2exe/py2exe/0.6.9/py2exe-0.6.9.win32-py2.7.exe",
        "Nose": "https://s3.amazonaws.com/geonodedeps/nose-1.3.3.win32-py2.7.exe",
        "LXML": "https://pypi.python.org/packages/2.7/l/lxml/lxml-3.3.5.win32-py2.7.exe",
        "GDAL": "https://s3.amazonaws.com/geonodedeps/GDAL-1.11.0.win32-py2.7.exe",
        "PyProj": "https://pyproj.googlecode.com/files/pyproj-1.9.3.win32-py2.7.exe",
        "Shapely": "https://pypi.python.org/packages/2.7/S/Shapely/Shapely-1.3.0.win32-py2.7.exe",
        "Psycopg2": "http://www.stickpeople.com/projects/python/win-psycopg/psycopg2-2.4.5.win32-py2.7-pg9.1.3-release.exe"
    }

    for package, url in win_packages.iteritems():
        tempfile = download_dir / os.path.basename(url)
        grab_winfiles(url, tempfile, package)
        try:
            easy_install.main([tempfile])
        except:
            print "install failed"
        os.remove(tempfile)
    print "Windows dependencies now complete.  Run pip install -e geonode --use-mirrors"


@cmdopts([
    ('version=', 'v', 'Legacy GeoNode version of the existing database.')
])
@task
def upgradedb(options):
    """
    Add 'fake' data migrations for existing tables from legacy GeoNode versions
    """
    version = options.get('version')
    if version in ['1.1', '1.2']:
        sh("python manage.py migrate maps 0001 --fake")
        sh("python manage.py migrate avatar 0001 --fake")
    elif version is None:
        print "Please specify your GeoNode version"
    else:
        print "Upgrades from version %s are not yet supported." % version


@task
def sync(options):
    """
    Run the syncdb and migrate management commands to create and migrate a DB
    """
    sh("python manage.py syncdb --noinput")
    #sh("python manage.py migrate --noinput")
    sh("python manage.py loaddata sample_admin.json")


@task
def package(options):
    """
    Creates a tarball to use for building the system elsewhere
    """
    import pkg_resources
    import tarfile
    import geonode

    version = geonode.get_version()
    # Use GeoNode's version for the package name.
    pkgname = 'GeoNode-%s-all' % version

    # Create the output directory.
    out_pkg = path(pkgname)
    out_pkg_tar = path("%s.tar.gz" % pkgname)

    # Create a distribution in zip format for the geonode python package.
    dist_dir = path('dist')
    dist_dir.rmtree()
    sh('python setup.py sdist --formats=zip')

    with pushd('package'):

        #Delete old tar files in that directory
        for f in glob.glob('GeoNode*.tar.gz'):
            old_package = path(f)
            if old_package != out_pkg_tar:
                old_package.remove()

        if out_pkg_tar.exists():
            info('There is already a package for version %s' % version)
            return

        # Clean anything that is in the oupout package tree.
        out_pkg.rmtree()
        out_pkg.makedirs()

        support_folder = path('support')
        install_file = path('install.sh')

        # And copy the default files from the package folder.
        justcopy(support_folder, out_pkg / 'support')
        justcopy(install_file, out_pkg)

        geonode_dist = path('..') / 'dist' / 'GeoNode-%s.zip' % version
        justcopy(geonode_dist, out_pkg)

        # Create a tar file with all files in the output package folder.
        tar = tarfile.open(out_pkg_tar, "w:gz")
        for file in out_pkg.walkfiles():
            tar.add(file)

        # Add the README with the license and important links to documentation.
        tar.add('README', arcname=('%s/README.rst' % out_pkg))
        tar.close()

        # Remove all the files in the temporary output package directory.
        out_pkg.rmtree()

    # Report the info about the new package.
    info("%s created" % out_pkg_tar.abspath())


@task
@needs(['start_geoserver',
        'sync',
        'start_django'])
@cmdopts([
    ('bind=', 'b', 'Bind server to provided IP address and port number.'),
    ('java_path=', 'j', 'Full path to java install for Windows')
], share_with=['start_django', 'start_geoserver'])
def start():
    """
    Start GeoNode (Django, GeoServer & Client)
    """
    info("GeoNode is now available.")


@task
def stop_django():
    """
    Stop the GeoNode Django application
    """
    kill('python', 'runserver')


@task
def stop_geoserver():
    """
    Stop GeoServer
    """
    kill('java', 'geoserver')


@task
def stop():
    """
    Stop GeoNode
    """
    #windows needs to stop the geoserver first b/c we can't tell which python is running, so we kill everything
    stop_geoserver()
    info("Stopping GeoNode ...")
    stop_django()


@cmdopts([
    ('bind=', 'b', 'Bind server to provided IP address and port number.')
])
@task
def start_django():
    """
    Start the GeoNode Django application
    """
    bind = options.get('bind', '')
    sh('python manage.py runserver %s &' % bind)


@cmdopts([
    ('java_path=', 'j', 'Full path to java install for Windows')
])
@task
def start_geoserver(options):
    """
    Start GeoServer with GeoNode extensions
    """

    from geonode.settings import OGC_SERVER
    GEOSERVER_BASE_URL = OGC_SERVER['default']['LOCATION']

    url = "http://localhost:8080/geoserver/"
    if GEOSERVER_BASE_URL != url:
        print 'your GEOSERVER_BASE_URL does not match %s' % url
        sys.exit(1)

    download_dir = path('downloaded').abspath()
    jetty_runner = download_dir / os.path.basename(JETTY_RUNNER_URL)
    data_dir = path('geoserver/data').abspath()
    web_app = path('geoserver/geoserver').abspath()
    log_file = path('geoserver/jetty.log').abspath()
    config = path('scripts/misc/jetty-runner.xml').abspath()
    # @todo - we should not have set workdir to the datadir but a bug in geoserver
    # prevents geonode security from initializing correctly otherwise
    with pushd(data_dir):
        javapath = "java"
        loggernullpath = "/dev/null"
        try:
            sh(('java -version'))
        except:
            if not options.get('java_path', None):
                print "Paver cannot find java in the Windows Environment.  Please provide the --java_path flag with your full path to java.exe e.g. --java_path=C:/path/to/java/bin/java.exe"
                sys.exit(1)
            # if there are spaces
            javapath = 'START /B "" "' + options['java_path'] + '"'
            # cmd log file needs to exist in windows
            # using folder from .gitignore
            open("../../downloaded/null.txt", 'w+').close()
            loggernullpath = "../../downloaded/null.txt"

        sh((
            '%(javapath)s -Xmx512m -XX:MaxPermSize=256m'
            ' -DGEOSERVER_DATA_DIR=%(data_dir)s'
            # workaround for JAI sealed jar issue and jetty classloader
            ' -Dorg.eclipse.jetty.server.webapp.parentLoaderPriority=true'
            ' -jar %(jetty_runner)s'
            ' --log %(log_file)s'
            ' %(config)s'
            ' > %(loggernullpath)s &' % locals()
        ))

    info('Starting GeoServer on %s' % url)

    # wait for GeoServer to start
    started = waitfor(url)
    info('The logs are available at %s' % log_file)

    if not started:
        # If applications did not start in time we will give the user a chance
        # to inspect them and stop them manually.
        info(('GeoServer never started properly or timed out.'
              'It may still be running in the background.'))
        sys.exit(1)


@task
def test(options):
    """
    Run GeoNode's Unit Test Suite
    """
    sh("python manage.py test %s.tests --noinput" % '.tests '.join(GEONODE_APPS))


@task
def test_javascript(options):
    with pushd('geonode/static/geonode'):
        sh('./run-tests.sh')


@task
@cmdopts([
    ('name=', 'n', 'Run specific tests.')
    ])
def test_integration(options):
    """
    Run GeoNode's Integration test suite against the external apps
    """
    _reset()
    # Start GeoServer
    call_task('start_geoserver')
    info("GeoNode is now available, running the tests now.")

    name = options.get('name', 'geonode.tests.integration')

    success = False
    try:
        if name == 'geonode.tests.csw':
            call_task('start')
            sh('sleep 30')
            call_task('setup_data')
        sh(('python manage.py test %s'
           ' --noinput --liveserver=localhost:8000' % name))
    except BuildFailure, e:
        info('Tests failed! %s' % str(e))
    else:
        success = True
    finally:
        # don't use call task here - it won't run since it already has
        stop()

    _reset()
    if not success:
        sys.exit(1)

@task
def run_tests():
    """
    Executes the entire test suite.
    """
    sh('python manage.py test geonode.tests.smoke')
    call_task('test')
    call_task('test_integration')
    call_task('test_integration', options={'name': 'geonode.tests.csw'})
    sh('flake8 geonode')

@task
@needs(['stop'])
def reset():
    """
    Reset a development environment (Database, GeoServer & Catalogue)
    """
    _reset()


def _reset():
    sh("rm -rf geonode/development.db")
    sh("rm -rf geonode/uploaded/*")
    _install_data_dir()


@needs(['reset'])
def reset_hard():
    """
    Reset a development environment (Database, GeoServer & Catalogue)
    """
    sh("git clean -dxf")


@task
@cmdopts([
    ('type=', 't', 'Import specific data type ("vector", "raster", "time")'),
])
def setup_data():
    """
    Import sample data (from gisdata package) into GeoNode
    """
    import gisdata

    ctype = options.get('type', None)

    data_dir = gisdata.GOOD_DATA

    if ctype in ['vector', 'raster', 'time']:
        data_dir = os.path.join(gisdata.GOOD_DATA, ctype)

    sh("python manage.py importlayers %s -v2" % data_dir)


@needs(['package'])
@cmdopts([
    ('key=', 'k', 'The GPG key to sign the package'),
    ('ppa=', 'p', 'PPA this package should be published to.'),
])
def deb(options):
    """
    Creates debian packages.

    Example uses:
        paver deb
        paver deb -k 12345
        paver deb -k 12345 -p geonode/testing
    """
    key = options.get('key', None)
    ppa = options.get('ppa', None)

    version, simple_version = versions()

    info('Creating package for GeoNode version %s' % version)

    # Get rid of any uncommitted changes to debian/changelog
    info('Getting rid of any uncommitted changes in debian/changelog')
    sh('git checkout package/debian/changelog')

    # Workaround for git-dch bug
    # http://bugs.debian.org/cgi-bin/bugreport.cgi?bug=594580
    sh('ln -s %s %s' % (os.path.realpath('.git'), os.path.realpath('package')))

    with pushd('package'):

        # Install requirements
        #sh('sudo apt-get -y install debhelper devscripts git-buildpackage')

        sh(('git-dch --spawn-editor=snapshot --git-author --new-version=%s'
            ' --id-length=6 --ignore-branch --release' % (simple_version)))

        deb_changelog = path('debian') / 'changelog'
        for line in fileinput.input([deb_changelog], inplace=True):
            print line.replace("urgency=medium", "urgency=high"),

        ## Revert workaround for git-dhc bug
        sh('rm -rf .git')

        if key is None and ppa is None:
            # A local installable package
            sh('debuild -uc -us -A')
        elif key is None and ppa is not None:
                # A sources package, signed by daemon
                sh('debuild -S')
        elif key is not None and ppa is None:
                # A signed installable package
                sh('debuild -k%s -A' % key)
        elif key is not None and ppa is not None:
                # A signed, source package
                sh('debuild -k%s -S' % key)

    if ppa is not None:
        sh('dput ppa:%s geonode_%s_source.changes' % (ppa, simple_version))


@task
def publish():
    if 'GPG_KEY_GEONODE' in os.environ:
        key = os.environ['GPG_KEY_GEONODE']
    else:
        print "You need to set the GPG_KEY_GEONODE environment variable"
        return

    call_task('deb', options={
        'key': key,
        'ppa': 'geonode/testing',
    })

    version, simple_version = versions()
    sh('git add package/debian/changelog')
    sh('git commit -m "Updated changelog for version %s"' % version)
    sh('git tag %s' % version)
    sh('git push origin %s' % version)
    sh('git tag debian/%s' % simple_version)
    sh('git push origin debian/%s' % simple_version)
    sh('git push origin master')
    sh('python setup.py sdist upload')


def versions():
    import geonode
    from geonode.version import get_git_changeset
    raw_version = geonode.__version__
    version = geonode.get_version()
    timestamp = get_git_changeset()

    major, minor, revision, stage, edition = raw_version

    branch = 'dev'

    if stage == 'final':
        stage = 'thefinal'

    if stage == 'alpha' and edition == 0:
        tail = '%s%s' % (branch, timestamp)
    else:
        tail = '%s%s' % (stage, edition)

    simple_version = '%s.%s.%s+%s' % (major, minor, revision, tail)
    return version, simple_version


def kill(arg1, arg2):
    """Stops a proces that contains arg1 and is filtered by arg2
    """
    from subprocess import Popen, PIPE

    # Wait until ready
    t0 = time.time()
    # Wait no more than these many seconds
    time_out = 30
    running = True

    while running and time.time() - t0 < time_out:
        if os.name == 'nt':
            p = Popen('tasklist | find "%s"' % arg1, shell=True,
                      stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=False)
        else:
            p = Popen('ps aux | grep %s' % arg1, shell=True,
                      stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)

        lines = p.stdout.readlines()

        running = False
        for line in lines:
            #this kills all java.exe and python including self in windows
            if ('%s' % arg2 in line) or (os.name == 'nt' and '%s' % arg1 in line):
                running = True

                # Get pid
                fields = line.strip().split()

                info('Stopping %s (process number %s)' % (arg1, fields[1]))
                if os.name == 'nt':
                    kill = 'taskkill /F /PID "%s"' % fields[1]
                else:
                    kill = 'kill -9 %s 2> /dev/null' % fields[1]
                os.system(kill)

        # Give it a little more time
        time.sleep(1)
    else:
        pass

    if running:
        raise Exception('Could not stop %s: '
                        'Running processes are\n%s'
                        % (arg1, '\n'.join([l.strip() for l in lines])))


def waitfor(url, timeout=300):
    started = False
    for a in xrange(timeout):
        try:
            resp = urllib.urlopen(url)
        except IOError:
            pass
        else:
            if resp.getcode() == 200:
                started = True
                break
        time.sleep(1)
    return started


def justcopy(origin, target):
    if os.path.isdir(origin):
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(origin, target)
    elif os.path.isfile(origin):
        if not os.path.exists(target):
            os.makedirs(target)
        shutil.copy(origin, target)
