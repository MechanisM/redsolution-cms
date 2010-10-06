# -*- coding: utf-8 -*-
import os
from os.path import abspath, join, dirname
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.template.loader import render_to_string
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_syncdb
from redsolutioncms.loader import home_dir, project_dir

class BaseSettingsManager(models.Manager):
    def get_settings(self):
        if self.get_query_set().count():
            return self.get_query_set()[0]
        else:
            return self.get_query_set().create()

class BaseSettings(models.Model):
    class Meta:
        abstract = True
    objects = BaseSettingsManager()

class CMSSettings(BaseSettings):
    DATABASE_ENGINES = [
        ('postgresql_psycopg2', 'postgresql_psycopg2',),
        ('postgresql', 'postgresql',),
        ('mysql', 'mysql',),
        ('sqlite3', 'sqlite3',),
        ('oracle', 'oracle',),
    ]

    initialized = models.BooleanField(verbose_name=_('CMS was initialized'), default=False)
    project_name = models.CharField(verbose_name=_('Project name'), max_length=50, default='myproject')
    database_engine = models.CharField(verbose_name=_('Database engine'), max_length=50, choices=DATABASE_ENGINES, default='sqlite3')
    database_name = models.CharField(verbose_name=_('Database name'), max_length=50, default='example.sqlite')
    database_user = models.CharField(verbose_name=_('Database user'), max_length=50, blank=True, default='')
    database_password = models.CharField(verbose_name=_('Database password'), max_length=50, blank=True, default='')
    database_host = models.CharField(verbose_name=_('Database host'), max_length=50, blank=True, default='')
    database_port = models.IntegerField(verbose_name=_('Database port'), blank=True, null=True)
    base_template = models.CharField(verbose_name=_('Base template'), max_length=50, blank=True, default='')
    frontpage_handler = models.ForeignKey('CMSEntryPoint', related_name='settings', null=True)

    def render_to(self, file_name, template_name, dictionary=None, mode='a+'):
        """
        ``file_name`` is relative path to destination file.
            It can be list or tuple to be os.path.joined
            To make settings.py use: 'settings.py'
            To make template use: ['..', 'templates', 'base.html']
            To make media use: ['..', 'media', 'css', 'style.css']
        
        ``template_name`` is name of template to be rendered.
        
        ``dictionary`` is context dictionary.
            ``cms_settings`` variable always will be add to context.
        
         ``mode`` is mode in witch destination file will be opened.
             Use 'w' to override old content.
        """
        if isinstance(file_name, (tuple, list)):
            file_name = join(*file_name)
        file_name = join(project_dir, self.project_name, file_name)
        try:
            os.makedirs(dirname(file_name))
        except OSError:
            pass
        if dictionary is None:
            dictionary = {}
        dictionary['cms_settings'] = self
        value = render_to_string(template_name, dictionary)
        value = value.encode('utf-8')
        open(file_name, mode).write(value)

    def package_was_installed(self, package_name):
        return package_name in self.installed_packages

    @property
    def installed_packages(self):
        return self.packages.installed().values_list('package', flat=True)

    @property
    def project_dir(self):
        import warnings
        warnings.warn('Project dir is deprecated attribute. Use redsolutioncms.loader.project_dir instead')
        return project_dir

    @property
    def temp_dir(self):
        import warnings
        warnings.warn('Project dir is deprecated attribute. Use redsolutioncms.loader.home_dir instead')
        return home_dir

class PackageManager(models.Manager):

    def installed(self):
        return self.get_query_set().filter(installed=True)

    def modules(self):
        return self.get_query_set().filter(template=False)

    def templates(self):
        return self.get_query_set().filter(template=True)

class CMSPackage(models.Model):
    class Meta:
        unique_together = (
            ('settings', 'package',),
        )
    settings = models.ForeignKey(CMSSettings, related_name='packages')

    selected = models.BooleanField(verbose_name=_('Selected'), default=False)
    package = models.CharField(verbose_name=_('Package'), max_length=255)
    version = models.CharField(verbose_name=_('Package version'), max_length=50)
    verbose_name = models.CharField(verbose_name=_('Verbose name'), max_length=255)
    description = models.TextField(verbose_name=_('Description'))
    path = models.CharField(verbose_name=_('Installed to path'), max_length=255, blank=True, null=True)
    installed = models.BooleanField(verbose_name=_('Was successfully installed'), default=False)

    template = models.BooleanField(verbose_name=_('Package is template'), default=False)
    screenshot = models.URLField(verbose_name=_('Screenshot preview URL'), null=True)

    objects = PackageManager()

    def __unicode__(self):
        return self.package

class EntryPointManager(models.Manager):
    def has_urls(self):
        return self.get_query_set().filter(has_urls=True)

    def frontpage_handlers(self):
        return self.get_query_set().filter(frontpage_handler=True)

class CMSEntryPoint(models.Model):
    package = models.ForeignKey(CMSPackage, related_name='entry_points')
    module = models.CharField(verbose_name=_('Module name'), max_length=255)
    has_urls = models.BooleanField(verbose_name=_('Has urls'))
    frontpage_handler = models.BooleanField(verbose_name=_('Can handle frontpage'))

    objects = EntryPointManager()

    def __unicode__(self):
        return 'Entry point %s' % self.module

class CMSCreatedModel(models.Model):
    name = models.CharField(verbose_name=_('Name'), max_length=100, unique=True)

    def __unicode__(self):
        return self.name

class ProcessTask(models.Model):
    task = models.CharField(verbose_name=_('task'), max_length=255)
    pid = models.IntegerField(verbose_name=_('process pid'), blank=True, null=True)
    lock = models.BooleanField(verbose_name=_('task inactive'), default=False)
    executed = models.BooleanField(verbose_name=_('task executed'), default=False)
    process_finished = models.BooleanField(verbose_name=_('process finished'), default=False)
    wait = models.BooleanField(verbose_name=_('wait finish'), default=False)

    def __unicode__(self):
        return self.task

def add_created_model(created_models, **kwargs):
    cms_settings = CMSSettings.objects.get_settings()
    if cms_settings.initialized:
        for model in created_models:
            CMSCreatedModel.objects.get_or_create(name='%s.%s' % (model.__module__, model.__name__))

post_syncdb.connect(add_created_model)
