#!/usr/bin/env python3

import mw, config, hashlib, re, requests, os, shutil, subprocess, sys, tempfile
import code

wiki = mw.Wiki(config.API_PHP)

sys.stderr.write('Logging into %s...\n' % config.WIKI)
wiki.login(config.USERNAME, config.PASSWORD)

# obtain
sys.stderr.write('Fetching pages from %s...\n' % config.API_PHP)
try:
  pages = wiki.request({
    'action': 'query',
    'prop': 'imageinfo',
    'iiprop': '|'.join([ 'user', 'url', 'mime' ]),
    'generator': 'categorymembers',
    'gcmtitle': config.CATEGORY,
  })['query']['pages']
except mw.SSMWError as e:
  if e.args[0] == '[]':
    sys.stderr.write('!!! %s is empty !!!\n' % config.CATEGORY)
  raise e

images = {
  'image/png': [],
  'image/jpeg': [],
  'image/gif': [],
}

# download & sort
for (pageid, image) in pages.items():
  if not 'imageinfo' in image:
    continue
  imageinfo = image['imageinfo'][0]
  url = imageinfo['url']
  sys.stderr.write('Fetching %s...\n' % url)
  r = requests.get(url, stream=True)

  f = tempfile.NamedTemporaryFile(suffix=os.path.splitext(image['title'])[1], delete=False)
  shutil.copyfileobj(r.raw, f)
  del r

  images[imageinfo['mime']].append((image, f.name))

# optimize

for mime in images:
  optimisers = {
    'image/png': [[config.OPTIPNG] + config.OPTIPNG_OPTIONS, [config.ZOPFLIPNG, '-y', '--prefix'] + config.ZOPFLIPNG_OPTIONS],
    'image/gif': [[config.GIFSICLE, '--batch'] + config.GIFSICLE_OPTIONS],
    'image/jpeg': [[config.JPEGOPTIM] + config.JPEGOPTIM_OPTIONS],
  }

  if images[mime]:
    sys.stderr.write('Optimising %s images\n' % mime)
    for optimiser in optimisers[mime]:
      print(optimiser + [image[1] for image in images[mime]])
      if subprocess.call(optimiser + [image[1] for image in images[mime]]):
        raise Exception('Optimising failed')

# upload

tokens = wiki.request({
  'action': 'query',
  'prop': 'info|revisions',
  'rvprop': 'content',
  'intoken': 'edit',
  'pageids': pages.keys(),
})['query']['pages']

for mime in images:
  for (image, f) in images[mime]:
    sys.stderr.write('Uploading %s to %s...\n' % (f, image['title']))

    pageid = str(image['pageid'])
    upload = wiki.request(data={
      'action': 'upload',
      'filename': image['title'],
      'comment': config.COMMENT,
      'text': config.COMMENT,
      'token': tokens[pageid]['edittoken'],
      'ignorewarnings': True,
    }, post=True, files={
      'file': open(f, 'rb')
    })['upload']

    r = requests.get(upload['imageinfo']['descriptionurl'], params={
      'action': 'raw'
    })

    text = re.sub(config.REMOVE, '', r.text, flags=re.I)

    edit = wiki.request(data={
      'action': 'edit',
      'pageid': image['pageid'],
      'text': text,
      'bot': True,
      'nocreate': True,
      'token': tokens[pageid]['edittoken'],
    }, post=True)

