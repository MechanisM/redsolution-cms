from django.conf import settings
from django.core.urlresolvers import reverse
from django.forms.models import modelform_factory
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from redsolutioncms.forms import CMSPackagesForm, UserCreationForm
from redsolutioncms.importpath import importpath
from redsolutioncms.loader import home_dir, process_cmd_string, project_dir
from redsolutioncms.make import AlreadyMadeException
from redsolutioncms.models import CMSSettings, CMSEntryPoint, CMSCreatedModel, \
    ProcessTask
from redsolutioncms.packages import search_index, install
import os

CONFIG_FILES = ['manage', 'settings', 'urls', ]

def list_packages():
    """
    Creates objects in CMSPackages model for all modules at PYPI
    """
    cms_settings = CMSSettings.objects.get_settings()
    all_packages = search_index('redsolutioncms')

    if not cms_settings.packages.count():
        for package in all_packages:
            cms_settings.packages.create(
                selected=False,
                package=package['name'],
                version=package['version'],
                verbose_name=package['name'].replace('django-', '').replace('redsolutioncms.', ''),
                description=package['summary']
            )

def index(request):
    """
    Shows greetings form, base settings form: project name, database settings, etc.
    """
    cms_settings = CMSSettings.objects.get_settings()
    cms_settings.initialized = True
    cms_settings.save()
    SettingsForm = modelform_factory(CMSSettings, exclude=['initialized'])
    if request.method == 'POST':
        form = SettingsForm(data=request.POST, files=request.FILES, instance=cms_settings)
        if form.is_valid():
            form.save(commit=True)
            return HttpResponseRedirect(reverse('apps'))
    else:
        form = SettingsForm(instance=cms_settings)
    return render_to_response('redsolutioncms/index.html', {
        'form': form,
    }, context_instance=RequestContext(request))

def apps(request):
    """
    Second step. Shows available packages listing.
    """
    list_packages()
    if request.method == 'POST':
        form = CMSPackagesForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('load'))
    else:
        form = CMSPackagesForm()
    return render_to_response('redsolutioncms/apps.html', {
        'form': form,
    }, context_instance=RequestContext(request))

def load(request):
    """
    Show wait circle loader, fetch packages from index site.
    Template has AJAX checker, so user will be redirected to next step automatically.
    Saves installation information for packages.
    Makes settings.py, urls.py, manage.py with installed setup-packages.
    Syncdb for setup-packages.
    """
    task = ProcessTask.objects.create(
        task=process_cmd_string('%(django)s kill_runserver'),
        lock=True, wait=True)
    ProcessTask.objects.create(task=process_cmd_string('%(django)s install_packages'), wait=True)
    ProcessTask.objects.create(task=process_cmd_string('%(django)s change_settings'), wait=True)
    ProcessTask.objects.create(task=process_cmd_string('%(django)s syncdb --noinput'), wait=True)
    ProcessTask.objects.create(task=process_cmd_string('%(django)s runserver --noreload'))
    return render_to_response('redsolutioncms/wait.html', {
        'task_id':task.id,
        'redirect_to': reverse('custom'),
        'start_task_id':task.id,
        'title': _('Downloading packages'),
    }, context_instance=RequestContext(request))

def custom(request):
    """
    User can go to detail settings for packages or can ask to make project.
    Make files for new project.
    """
    cms_settings = CMSSettings.objects.get_settings()
    if request.method == 'POST':
        entry_points = ['redsolutioncms']
        cms_settings.head_blocks.all().delete()
        cms_settings.top_blocks.all().delete()
        cms_settings.left_blocks.all().delete()
        cms_settings.center_blocks.all().delete()
        cms_settings.right_blocks.all().delete()
        cms_settings.bottom_blocks.all().delete()
        for package in cms_settings.packages.installed():
            for entry_point in package.entry_points.all():
                entry_points.append(entry_point.module)
        make_objects = []
        for entry_point in entry_points:
            try:
                make_object = importpath('.'.join([entry_point, 'make', 'make']))
            except ImportError, error:
                print 'Entry point %s has no make object.' % entry_point
                continue
            make_objects.append(make_object)
        for make_object in make_objects:
            make_object.flush()
        for make_object in make_objects:
            try:
                make_object.premake()
            except AlreadyMadeException:
                pass
        for make_object in make_objects:
            try:
                make_object.make()
            except AlreadyMadeException:
                pass
        for make_object in make_objects:
            try:
                make_object.postmake()
            except AlreadyMadeException:
                pass
        return HttpResponseRedirect(reverse('build'))
    return render_to_response('redsolutioncms/custom.html', {
        'cms_settings': cms_settings,
    }, context_instance=RequestContext(request))

def build(request):
    cms_settings = CMSSettings.objects.get_settings()
    task = ProcessTask.objects.create(
        task=process_cmd_string('%(django)s kill_runserver'),
        lock=True, wait=True)
    
    project_params = {
        'project_bootstrap': os.path.join(project_dir, 'bootstrap.py'),
        'project_buildout': os.path.join(project_dir, 'bin', 'buildout'),
        'project_django': os.path.join(project_dir, 'bin', 'django'),            
    }

    print 'BARBARBAR'
    print project_dir
    print process_cmd_string('%(python)s %(project_bootstrap)s', project_params)
    print process_cmd_string('%(python)s %(project_buildout)s -c develop.cfg', project_params)
    print process_cmd_string('%(project_django)s syncdb --noinput', project_params)
    print process_cmd_string('%(project_django)s runserver 8001 --noreload', project_params)
    print process_cmd_string('%(django)s runserver --noreload')

    ProcessTask.objects.create(
        task=process_cmd_string('%(python)s %(project_bootstrap)s', project_params),
        wait=True)
    ProcessTask.objects.create(
        task=process_cmd_string('%(python)s %(project_buildout)s -c develop.cfg', project_params),
        wait=True)
    ProcessTask.objects.create(
        task=process_cmd_string('%(project_django)s syncdb --noinput', project_params),
        wait=True)
    ProcessTask.objects.create(
        task=process_cmd_string('%(project_django)s runserver 8001 --noreload', 
        project_params))
    ProcessTask.objects.create(
        task=process_cmd_string('%(django)s runserver --noreload'))

    return render_to_response('redsolutioncms/wait.html',
        {'task_id': task.id, 'redirect_to': reverse('create_superuser'),
            'start_task_id':task.id},
         context_instance=RequestContext(request))

def create_superuser(request):
    cms_settings = CMSSettings.objects.get_settings()
    if request.method == 'POST':
        form = UserCreationForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            django_name = os.path.join(project_dir, 'bin', 'django')
            if os.sys.platform == 'win32':
                # TODO: do something
                return HttpResponseRedirect(reverse('done'))
            else:
                import pexpect
                # TODO: Wrong dir again! Agrhhh!!!
                child = pexpect.spawn('python %s createsuperuser' % django_name,
                    timeout=3)
                child.expect("Username.*")
                child.sendline(form.cleaned_data['username'])
                try:
                    child.expect("E-mail.*")
                except pexpect.TIMEOUT:
                    from django import forms
                    form.errors['username'] = [_('This username is busy.')]
                else:
    #                child.expect("E-mail.*")
                    child.sendline(form.cleaned_data['email'])
                    child.expect("Password.*")
                    child.sendline(form.cleaned_data['password1'])
                    child.expect("Password.*")
                    child.sendline(form.cleaned_data['password1'])
                    child.expect("Superuser.*")
                    return HttpResponseRedirect(reverse('done'))
    else:
        form = UserCreationForm()
    return render_to_response('redsolutioncms/build.html', {
        'cms_settings': cms_settings,
        'bootstrap': os.path.join(project_dir, 'bootstrap.py'),
        'buildout': os.path.join(project_dir, 'bin', 'buildout'),
        'django': os.path.join(project_dir, 'bin', 'django'),
        'form': form,
    }, context_instance=RequestContext(request))

def done(request):
    cms_settings = CMSSettings.objects.get_settings()
    return render_to_response('redsolutioncms/done.html', {
        'cms_settings': cms_settings,
        'project_dir': project_dir,
        'django': os.path.join(project_dir, 'bin', 'django'),
    }, context_instance=RequestContext(request))

def restart(request):
    """
    Ajax view. Restarts runserver
    """
    task = ProcessTask.objects.create(task=process_cmd_string('%(django)s kill_runserver'),
        lock=True, wait=True)
    ProcessTask.objects.create(task=process_cmd_string('%(django)s runserver --noreload'))
    task.lock = False
    task.save()
    return HttpResponse()

def started(request, task_id):
    """
    User can`t see it. It will be called by javascript.
    Used to check, whether server is available after restart.
    """
    task = ProcessTask.objects.get(id=task_id)
    if task.process_finished:
        return HttpResponse()

def cancel_lock(request, task_id):
    task = ProcessTask.objects.get(id=task_id)
    task.lock = False
    task.save()
    return HttpResponse()
