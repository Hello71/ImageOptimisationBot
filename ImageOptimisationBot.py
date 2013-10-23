#!/usr/bin/env python3

import mw, config, multiprocessing, re, requests, os, shutil, subprocess, sys, tempfile

wiki = mw.Wiki(config.API_PHP)

sys.stderr.write('Logging into %s...\n' % config.WIKI)
wiki.login(config.USERNAME, config.PASSWORD)

# obtain
sys.stderr.write('Fetching pages from %s...\n' % config.API_PHP)
try:
  pages = wiki.request({
    'action': 'query',
    'prop': 'info|revisions|imageinfo',
    'intoken': 'edit',
    'rvprop': 'content',
    'iiprop': 'user|url|mime',
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

optimisers = {
  'image/png': [[config.OPTIPNG] + config.OPTIPNG_OPTIONS, [config.ZOPFLIPNG, '-y', '--prefix'] + config.ZOPFLIPNG_OPTIONS],
  'image/gif': [[config.GIFSICLE, '--batch'] + config.GIFSICLE_OPTIONS],
  'image/jpeg': [[config.JPEGOPTIM] + config.JPEGOPTIM_OPTIONS],
}

def work(page):
  if not 'imageinfo' in page:
    return
  imageinfo = page['imageinfo'][0]
  url = imageinfo['url']
  sys.stderr.write('Fetching %s...\n' % url)
  r = requests.get(url, stream=True)

  with tempfile.NamedTemporaryFile(suffix=os.path.splitext(page['title'])[1]) as f:
    shutil.copyfileobj(r.raw, f)
    del r

    images[imageinfo['mime']].append((page, f.name))

    # optimise
    for optimiser in optimisers[imageinfo['mime']]:
      if subprocess.call(optimiser + [f.name]):
        raise Error("Optimising %s failed" % f.name)

    REMOVE = re.compile(config.REMOVE, re.IGNORECASE)

    # upload
    sys.stderr.write('Uploading %s to %s...\n' % (f.name, page['title']))

    page = pages[str(page['pageid'])]
    upload = wiki.request(data={
      'action': 'upload',
      'filename': page['title'],
      'comment': config.COMMENT,
      'text': config.COMMENT,
      'token': page['edittoken'],
      'ignorewarnings': True,
    }, post=True, files={
      'file': open(f.name, 'rb')
    })['upload']

    os.remove(f.name)

    # edit

    oldtext = page['revisions'][0]['*']
    newtext = re.sub(REMOVE, '', oldtext)

    if oldtext != newtext:
      sys.stderr.write('Editing %s to remove compression template...\n' % page['title'])

      edit = wiki.request(data={
        'action': 'edit',
        'pageid': page['pageid'],
        'starttimestamp': page['starttimestamp'],
        'text': newtext,
        'bot': True,
        'nocreate': True,
        'token': tokens[pageid]['edittoken'],
      }, post=True)

pool = multiprocessing.Pool()
pool.map(work, pages.values())

# upload
