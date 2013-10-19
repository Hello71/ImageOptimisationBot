#!/usr/bin/env python3

import mw, config, requests, os, shutil, subprocess, tempfile
import code

wiki = mw.Wiki(config.API_PHP)

print("Logging into %s..." % config.API_PHP)
wiki.login(config.USERNAME, config.PASSWORD)

# obtain
print("Fetching pages from %s..." % config.API_PHP)
pages = wiki.request({
  'action': 'query',
  'prop': 'imageinfo',
  'iiprop': '|'.join([ 'user', 'url', 'mime' ]),
  'generator': 'categorymembers',
  'gcmtitle': config.CATEGORY,
})['query']['pages']

images = {
  'image/png': [],
  'image/jpeg': [],
  'image/gif': [],
}

# download & sort
for (pageid, image) in pages.items():
  imageinfo = image['imageinfo'][0]
  url = imageinfo['url']
  print("Fetching %s..." % url)
  r = requests.get(url, stream=True)

  f = tempfile.NamedTemporaryFile(suffix=os.path.splitext(image['title'])[1], delete=False)
  shutil.copyfileobj(r.raw, f)
  del r

  images[imageinfo['mime']].append((image, f.name))

# optimize

for mime in images:
  optimisers = {
    'image/png': [['optipng'] + config.OPTIPNG_OPTIONS, ['zopflipng'] + config.ZOPFLIPNG_OPTIONS],
    'image/gif': [['gifsicle', '--batch'] + config.GIFSICLE_OPTIONS],
    'image/jpeg': [['jpegoptim'] + config.JPEGOPTIM_OPTIONS],
  }

  if images[mime]:
    for optimiser in optimisers[mime]:
      if subprocess.call(optimiser + [image[1] for image in images[mime]]):
        raise Exception("Optimising failed")

# upload

tokens = wiki.request({
  'action': 'query',
  'prop': 'info',
  'intoken': 'edit',
  'pageids': pages.keys(),
})['query']['pages']

for mime in images:
  for (image, f) in images[mime]:
    print("Uploading %s to %s..." % (image['title'], f))

    pageid = str(image['pageid'])
    wiki.request(data={
      'action': 'upload',
      'filename': image['title'],
      'comment': config.COMMENT,
      'text': config.COMMENT,
      'token': tokens[pageid]['edittoken'],
      'ignorewarnings': 1
    }, post=True, files={
      'file': open(f, 'rb')
    })

