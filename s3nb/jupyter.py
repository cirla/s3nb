import codecs
import datetime
import tempfile

import boto3
import botocore
from tornado import web

import nbformat
from notebook.services.contents.filecheckpoints import GenericFileCheckpoints
from notebook.services.contents.manager import ContentsManager
from traitlets.config import Config
from traitlets import Unicode


S3_SCHEME = 's3://'


def _parse_s3_uri(uri, delimiter):
    """
    Parse S3 URI and return tuple of (bucket_name, prefix)
    """

    if not uri.startswith(S3_SCHEME):
        raise Exception("Unexpected S3 URI scheme in '{}', expected s3://".format(uri))
    return uri[len(S3_SCHEME):].split(delimiter, 1)


class S3ContentsManager(ContentsManager):

    base_uri = Unicode(
        config=True,
        help="S3 base URI",
    )

    key_delimiter = Unicode(
        config=True,
        default_value='/',
        help="S3 key delimiter",
    )


    def __init__(self, **kwargs):
        super(S3ContentsManager, self).__init__(**kwargs)

        self.bucket_name, self.prefix = _parse_s3_uri(self.base_uri, self.key_delimiter)

        # ensure prefix ends with the delimiter
        if self.prefix and not self.prefix.endswith(self.key_delimiter):
            self.prefix += self.key_delimiter
        self.s3_resource = boto3.resource('s3')
        self.bucket = self.s3_resource.Bucket(self.bucket_name)
        self.log.debug("initialized base_uri: %s bucket: %s prefix: %s",
                       self.base_uri, self.bucket, self.prefix)


    def _path_to_s3_key(self, path):
        return self.prefix + path.strip(self.key_delimiter)


    def _path_to_s3_key_dir(self, path):
        key = self._path_to_s3_key(path)

        if path:
            key += self.key_delimiter

        return key


    def _get_key_dir_name(self, name):
        try:
            return name.rsplit(self.key_delimiter, 2)[-2]
        except IndexError:
            return ''

    def _s3_key_dir_to_model(self, key, content=False):
        self.log.debug("_s3_key_dir_to_model: %s: %s", key, key.key)
        model = {
            'name': self._get_key_dir_name(key.key),
            'path': key.key.replace(self.prefix, '', 1),
            'type': 'directory',
            'created': None,
            'last_modified': key.last_modified,
            'content': self._load_dir_content(key) if content else None,
            'mimetype': None,
            'format': 'json' if content else None,
            'writable': True,
        }

        self.log.debug("_s3_key_dir_to_model: %s: %s", key.key, model)
        return model

    def _s3_key_file_to_model(self, key, path, format, content=False):
        self.log.debug("_s3_key_file_to_model: %s: %s", key, key.key)
        model = {
            'name': key.key.rsplit(self.key_delimiter, 1)[-1],
            'path': key.key.replace(self.prefix, '', 1),
            'type': 'file',
            'created': None,
            'last_modified': key.last_modified,
            'content': self._load_file_content(key, path) if content else None,
            'mimetype': None,
            'format': format,
            'writable': True,
        }

        if content:
            model['mimetype'] = 'text/plain' if format == 'text' else 'application/octet-stream'

        self.log.debug("_s3_key_file_to_model: %s: %s", key.key, model)
        return model


    def _s3_key_notebook_to_model(self, key, path, content=False):
        self.log.debug("_s3_key_notebook_to_model: %s: %s", key, key.key)
        model = {
            'name': key.name.rsplit(self.key_delimiter, 1)[-1],
            'path': key.name.replace(self.prefix, '', 1),
            'type': 'notebook',
            'created': None,
            'last_modified': key.last_modified,
            'content': self._load_notebook_content(key, path) if content else None,
            'mimetype': None,
            'format': 'json' if content else None,
            'writable': True,
        }

        self.validate_notebook_model(model)

        self.log.debug("_s3_key_notebook_to_model: %s: %s", key.name, model)
        return model


    def _checkpoints_class_default(self):
        return GenericFileCheckpoints


    def _load_dir_content(self, key):
        self.log.debug('_load_dir_content: looking in bucket:%s under:%s', self.bucket.name, key.key)

        content = []
        for k in self.bucket.objects.filter(Delimiter=self.key_delimiter, Prefix=key.key):
            if k.key.endswith(self.key_delimiter) and k.key != key.key:
                content.append(self._s3_key_dir_to_model(k, content=False))
                self.log.debug('list_dirs: found %s', k.key)
            elif not k.key.endswith(self.key_delimiter) and not k.key.endswith('.ipynb') and k.key != key.key:
                content.append(self._s3_key_file_to_model(k, path=None, format=None, content=False))
                self.log.debug('list_files: found %s', k.key)
            elif k.name.endswith('.ipynb'):
                content.append(self._s3_key_notebook_to_model(k, path=None, content=False))
                self.log.debug('list_notebooks: found %s', k.key)

        return content


    def _load_notebook_content(self, key, path):
        try:
            with tempfile.NamedTemporaryFile() as t:
                t.write(key.get()['Body'].read())
                t.seek(0)

                with codecs.open(t.name, mode='r', encoding='utf-8') as f:
                    nb = nbformat.read(f, as_version=4)
        except Exception as e:
            raise web.HTTPError(400, u"Unreadable Notebook: {} {}".format(path, e))

        self.mark_trusted_cells(nb, path)
        return nb

    def _load_file_content(self, key, path):
        try:
            model['content'] = key.get()['Body'].read()
        except Exception as e:
            raise web.HTTPError(400, u"Unreadable file: {} {}".format(path, e))


    def get(self, path, content=True, type=None, format=None):

        # Directory
        if type == 'directory':
            key_str = self._path_to_s3_key_dir(path)
            key = self.bucket.Object(key_str)
            model = self._s3_key_dir_to_model(key, content)
            return model

        # Notebook
        if type == 'notebook' or (type is None and path.endswith('.ipynb')):
            key_str = self._path_to_s3_key(path)
            key = self.bucket.Object(key_str)
            model = self._s3_key_notebook_to_model(key, path, content)
            return model

        # File
        key_str = self._path_to_s3_key(path)
        key = self.bucket.Object(key_str)
        model = self._s3_key_file_to_model(key, path, format, content)
        return model


    def _save_file(self, path, content, format):
        key_str = self._path_to_s3_key(path)
        key = self.bucket.Object(key_str)

        key_str = self._path_to_s3_key(path)
        key = self.bucket.Object(key_str)

        try:
            with tempfile.NamedTemporaryFile() as t:
                t.write(content.encode('utf-8') if format == 'text' else content)
                t.seek(0)
                key.put(Body=t)
        except Exception as e:
            raise web.HTTPError(400, u"Unexpected Error Writing File: {} {}".format(path, e))


    def _save_notebook(self, path, nb):
        key_str = self._path_to_s3_key(path)
        key = self.bucket.Object(key_str)

        try:
            with tempfile.NamedTemporaryFile() as t, codecs.open(t.name, mode='w', encoding='utf-8') as f:
                nbformat.write(nb, f, version=nbformat.NO_CONVERT)
                t.seek(0)
                key.put(Body=t)
        except Exception as e:
            raise web.HTTPError(400, u"Unexpected Error Writing Notebook: {} {}".format(path, e))


    def save(self, model, path):
        if 'type' not in model:
            raise web.HTTPError(400, u'No file type provided')
        if 'content' not in model and model['type'] != 'directory':
            raise web.HTTPError(400, u'No file content provided')

        self.run_pre_save_hook(model=model, path=path)

        if model['type'] == 'notebook':
            nb = nbformat.from_dict(model['content'])
            self.check_and_sign(nb, path)
            self._save_notebook(path, nb)
        elif model['type'] == 'file':
            self._save_file(path, model['content'], model.get('format'))
        elif model['type'] == 'directory':
            pass
        else:
            raise web.HTTPError(400, "Unhandled contents type: {}".format(model['type']))

        validation_message = None
        if model['type'] == 'notebook':
            self.validate_notebook_model(model)
            validation_message = model.get('message', None)

        model = self.get(path, content=False, type=model['type'])
        if validation_message:
            model['message'] = validation_message

        return model


    def delete_file(self, path):
        key_str = self._path_to_s3_key(path)
        key = self.bucket.Object(key_str)
        self.log.debug('removing notebook in bucket: %s : %s', self.bucket.name, key_str)
        key.delete()


    def rename_file(self, old_path, new_path):
        if new_path == old_path:
            return

        src_key_str = self._path_to_s3_key(old_path)
        src_key = self.bucket.Object(src_key_str)
        dst_key_str = self._path_to_s3_key(new_path)
        dst_key = self.bucket.Object(dst_key_str)

        self.log.debug('copying file in bucket: %s from %s to %s', self.bucket.name, src_key.key, dst_key.key)

        dst_key.copy_from(CopySource={'Bucket': self.bucket.name, 'Key': src_key.key})
        self.log.debug('removing notebook in bucket: %s : %s', self.bucket.name, src_key.key)
        src_key.delete()


    def file_exists(self, path=''):
        if path == '':
            return False

        key_str = self._path_to_s3_key(path)
        key = self.bucket.Object(key_str)

        try:
            key.load()
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                return False
            else:
                raise

        return not key.key.endswith(self.key_delimiter)


    def dir_exists(self, path):
        if path == '':
            return True

        key = self._path_to_s3_key(path)
        if self.bucket.objects.filter(Delimiter=self.key_delimiter, Prefix=key.key, MaxKeys=1):
            return True

        return False


    def is_hidden(self, path):
        return False


    def new_untitled(self, path='', type='', ext=''):
        model = {
            'mimetype': None,
            'created': datetime.datetime.utcnow(),
            'last_modified': datetime.datetime.utcnow(),
            'writable': True,
        }

        if type:
            model['type'] = type

        if ext == '.ipynb':
            model.setdefault('type', 'notebook')
        else:
            model.setdefault('type', 'file')

        insert = ''
        if model['type'] == 'directory':
            untitled = self.untitled_directory
            insert = ' '
        elif model['type'] == 'notebook':
            untitled = self.untitled_notebook
            ext = '.ipynb'
        elif model['type'] == 'file':
            untitled = self.untitled_file
        else:
            raise web.HTTPError(400, "Unexpected model type: {}".format(model['type']))

        name = self.increment_filename(untitled + ext, self.prefix + path, insert=insert)
        path = u'{}{}{}'.format(path, self.key_delimiter, name)
        model.update({
            'name': name,
            'path': path,
        })

        return self.new(model, path)

