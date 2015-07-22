# noinspection PyUnresolvedReferences
import compressor_patch

from django.conf import settings
from django.contrib.staticfiles.finders import get_finders

import sass
from compressor.filters.base import FilterBase
from compressor.filters.css_default import CssAbsoluteFilter

OUTPUT_STYLE = getattr(settings, 'LIBSASS_OUTPUT_STYLE', 'nested')

# handle the differences in SOURCE_COMMENTS parameters between sass versions
SASS_SOURCE_COMMENTS_BOOL = tuple(int(a)
                                  for a in sass.__version__.split('.')) >= (0, 6, 0)

if SASS_SOURCE_COMMENTS_BOOL:
    SOURCE_COMMENTS = getattr(settings, 'LIBSASS_SOURCE_COMMENTS', settings.DEBUG)
    SOURCE_MAPS = getattr(settings, 'LIBSASS_SOURCE_MAPS', settings.DEBUG)
else:
    if settings.DEBUG:
        SOURCE_COMMENTS = getattr(settings, 'LIBSASS_SOURCE_COMMENTS', 'map')
    else:
        SOURCE_COMMENTS = getattr(settings, 'LIBSASS_SOURCE_COMMENTS', 'none')
    SOURCE_MAPS = SOURCE_COMMENTS == 'map'

def get_include_paths():
    """
    Generate a list of include paths that libsass should use to find files
    mentioned in @import lines.
    """
    include_paths = []

    # Look for staticfile finders that define 'storages'
    for finder in get_finders():
        try:
            storages = finder.storages
        except AttributeError:
            continue

        for storage in storages.values():
            try:
                include_paths.append(storage.path('.'))
            except NotImplementedError:
                # storages that do not implement 'path' do not store files locally,
                # and thus cannot provide an include path
                pass

    return include_paths


INCLUDE_PATHS = None  # populate this on first call to 'compile'

def compile(**kwargs):
    """Perform sass.compile, but with the appropriate include_paths for Django added"""
    global INCLUDE_PATHS
    if INCLUDE_PATHS is None:
        INCLUDE_PATHS = get_include_paths()

    kwargs = kwargs.copy()
    kwargs['include_paths'] = (kwargs.get('include_paths') or []) + INCLUDE_PATHS
    return sass.compile(**kwargs)

class SassCompiler(FilterBase):
    def __init__(self, content, attrs=None, filter_type=None, charset=None, filename=None):
        # FilterBase doesn't handle being passed attrs, so fiddle the signature
        super(SassCompiler, self).__init__(content, filter_type, filename)

    def input(self, **kwargs):
        kwargs.setdefault('filename', self.filename)
        kw = {'output_style': OUTPUT_STYLE}
        
        if self.filename:
            kw['filename'] = self.filename
            kw['source_comments'] = SOURCE_COMMENTS
            
            if SOURCE_MAPS:
                kw['source_map_filename'] = self.filename + '.map'
        else:
            kw['string'] = self.content
    
        if self.filename and SOURCE_MAPS:
            self.css, self.source_map = compile(**kw)
        else:
            self.css = compile(**kw)
        
        self.css = CssAbsoluteFilter(self.css).input(**kwargs)
        
        if self.filename and SOURCE_MAPS:
            return self.css, self.source_map
        else:
            return self.css

