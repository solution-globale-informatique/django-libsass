# ---
# Monkey patch for django compressor to handle source maps from django-libsass
# ---
from django.core.files.base import ContentFile
from django.utils.safestring import mark_safe
import compressor.base
import json

# Save original function for later, so we can send non-libsass output to the
# original function.
compressor.base.Compressor.___real_output_file = compressor.base.Compressor.output_file

def output_file(self, mode, content, forced=False, basename=None):
    """Libsass returns a 2-tuple of (css, map) from it's compile method.
    This value comes to us in the content variable above.

    TOOD: In order to make this realistic, it will be necessary to teach
    django-compressor that precompile steps (and others) can produce more than
    one file.

    This function takes advantage of the fact that content isn't touched until
    it gets to this function. Compressor needs to know what the css and map
    names are, so it can generate the correct file names.

    For now, we're assuming that the source map name is '<originalname.css>.map'
    Libsass handily stuffs the original file name at the end of the generated
    css, so we're extracting that name from the css to use as the map file name.

    This method will fail if the file name is really long, or the sourceMapURL
    is actually a url.
    """

    if not isinstance(content, tuple):
        return self.___real_output_file(mode, content, forced, basename)


    code, map = content

    code_filepath = self.get_filepath(code, basename=basename)
    if not self.storage.exists(code_filepath) or forced:
        self.storage.save(code_filepath, ContentFile(code.encode(self.charset)))

        # Determine the source map name by examining the css file.
        # and, assume that the reference to it lives in the last 200 chars of
        # the file (libsass puts it at the bottom).
        import re, os
        search = code[-200:]
        found = re.search(r'sourceMappingURL=([^ ]+)', search)
        if found:
            source_map_name = found.groups()[0]
            map_filepath = self.get_filepath(code, basename=source_map_name)
            # get_filepath returns a hashed filename, the map file was generated
            # with the original file name, so just grab the directory name from
            # get_filepath and then append the source map name we found in the
            # css.
            map_filepath = os.path.join(os.path.dirname(map_filepath), source_map_name)
            
            # Source maps are compiled assuming they are in the same folder as the
            # css output, but that output is written in COMPRESS_OUTPUT_DIR/css
            # instead. We need to fix source path in the source map file.
            map_content = json.loads(map)            
            for index, source in enumerate(map_content['sources']):
                map_content['sources'][index] = os.path.join(
                    os.path.relpath(os.path.dirname(basename), os.path.dirname(map_filepath)),
                    source
                )
            map = json.dumps(map_content)
            
            self.storage.save(map_filepath, ContentFile(map.encode(self.charset)))
        else:
            # Couldn't find the map name, so do nothing special
            pass

    url = mark_safe(self.storage.url(code_filepath))
    return self.render_output(mode, {"url": url})

# Apply patch
compressor.base.Compressor.output_file = output_file
