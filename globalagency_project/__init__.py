import pymysql
import sys
from copy import copy

from django import VERSION as DJANGO_VERSION
from django.template.context import BaseContext, Context

pymysql.install_as_MySQLdb()


def _patch_django_template_context_copy():
    """
    Django 4.2's BaseContext.__copy__ implementation is incompatible with
    Python 3.14's handling of ``copy(super())``. Patch it at startup so admin
    pages and any template rendering path that clones contexts keep working.
    """
    if sys.version_info < (3, 14) or DJANGO_VERSION[:2] != (4, 2):
        return

    def _base_context_copy(self):
        duplicate = object.__new__(self.__class__)
        duplicate.__dict__ = self.__dict__.copy()
        duplicate.dicts = self.dicts[:]
        return duplicate

    def _context_copy(self):
        duplicate = _base_context_copy(self)
        duplicate.render_context = copy(self.render_context)
        return duplicate

    BaseContext.__copy__ = _base_context_copy
    Context.__copy__ = _context_copy


_patch_django_template_context_copy()
