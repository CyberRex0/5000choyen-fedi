import logging
from misskey import Misskey
import websockets
import asyncio, aiohttp
import json
import datetime
import sys
import traceback
import re
import math
import time
import urllib.parse

try:
    import config_my as config
except ImportError:
    import config

from io import BytesIO

WS_URL = f'wss://{config.MISSKEY_INSTANCE}/streaming?i={config.MISSKEY_TOKEN}'
msk = Misskey(config.MISSKEY_INSTANCE, i=config.MISSKEY_TOKEN)
i = msk.i()

MY_ID = i['id']
print('Bot user id: ' + MY_ID)

session = aiohttp.ClientSession()
receivedNotes = set()

GSAPI_BASE = 'https://gsapi.cyberrex.jp'

async def on_post_note(note):
    pass

async def on_mention(note):
    # HTLとGTLを監視している都合上重複する恐れがあるため
    if note['id'] in receivedNotes:
        return

    receivedNotes.add(note['id'])

    command = False

    # 他のメンション取り除く
    split_text = note['text'].split(' ')
    new_st = []

    for t in split_text:
        if t.startswith('@'):
            pass
        else:
            new_st.append(t)

    note['text'] = ' '.join(new_st)
    note['text'] = note['text'].strip()

    #try:
    #    content = note['text'].strip().split(' ', 1)[1].strip()
    #    command = True
    #except IndexError:
    #    pass
    
    if note['text'] == 'ping':

        postdate = datetime.datetime.fromisoformat(note['createdAt'][:-1]).timestamp()
        nowdate = datetime.datetime.utcnow().timestamp()
        sa = nowdate - postdate
        text = f'{sa*1000:.2f}ms'
        msk.notes_create(text=text, reply_id=note['id'])

    else:

        lines = note['text'].split('\n')

        if len(lines) == 1:
            top_text = lines[0]
            query = {
                'top': top_text,
                'single': 'true'
            }
            print(urllib.parse.urlencode(query))
            async with session.get(GSAPI_BASE + '/image?' + urllib.parse.urlencode(query)) as r:
                if r.status != 200:
                    msk.notes_create(text=f'画像APIがステータスコード{r.status}で応答しました。(SL)', reply_id=note['id'])
                    return
                image = await r.read()
                try:
                    file = msk.drive_files_create(file=image, name=f'{datetime.datetime.utcnow().timestamp()}.png')
                except Exception as e:
                    if 'INTERNAL_ERROR' in str(e):
                        msk.notes_create('Internal Error occured in Misskey!', reply_id=note['id'])
                        return
                    if 'RATE_LIMIT_EXCEEDED' in str(e):
                        msk.notes_create('利用殺到による一時的なAPI制限が発生しました。しばらく時間を置いてから再度お試しください。', reply_id=note['id'])
                        return
                    msk.notes_create('画像アップロードに失敗しました\n```plaintext\n' + traceback.format_exc() + '\n```', reply_id=note['id'])
                    return
                
                msk.notes_create(text='.', reply_id=note['id'], file_ids=[file['id']])
        elif len(lines) >= 2:
            top_text = lines[0]
            bottom_text = lines[1]
            query = {
                'top': top_text,
                'bottom': bottom_text
            }
            async with session.get(GSAPI_BASE + '/image?' + urllib.parse.urlencode(query)) as r:
                if r.status != 200:
                    msk.notes_create(text=f'画像APIがステータスコード{r.status}で応答しました。(ML)', reply_id=note['id'])
                    return
                image = await r.read()
                try:
                    file = msk.drive_files_create(file=image, name=f'{datetime.datetime.utcnow().timestamp()}.png')
                except Exception as e:
                    if 'INTERNAL_ERROR' in str(e):
                        msk.notes_create('Internal Error occured in Misskey!', reply_id=note['id'])
                        return
                    if 'RATE_LIMIT_EXCEEDED' in str(e):
                        msk.notes_create('利用殺到による一時的なAPI制限が発生しました。しばらく時間を置いてから再度お試しください。', reply_id=note['id'])
                        return
                    msk.notes_create('画像アップロードに失敗しました\n```plaintext\n' + traceback.format_exc() + '\n```', reply_id=note['id'])
                    return
                
                msk.notes_create(text='.', reply_id=note['id'], file_ids=[file['id']])


            

async def on_followed(user):
    try:
        msk.following_create(user['id'])
    except:
        pass

async def main():

    print('Connecting to ' + config.MISSKEY_INSTANCE + '...', end='')
    async with websockets.connect(WS_URL) as ws:
        print('OK')
        
        #print('Attemping to watching timeline...', end='')
        #print('OK')
        p = {
            'type': 'connect',
            'body': {
                'channel': 'main'
            }
        }
        await ws.send(json.dumps(p))
        
        print('Listening ws')
        while True:
            data = await ws.recv()
            j = json.loads(data)
            # print(j)

            if j['type'] == 'channel':

                if j['body']['type'] == 'note':
                    note = j['body']['body']
                    try:
                        await on_post_note(note)
                    except Exception as e:
                        print(traceback.format_exc())
                        continue

                if j['body']['type'] == 'mention':
                    note = j['body']['body']
                    try:
                        await on_mention(note)
                    except Exception as e:
                        print(traceback.format_exc())
                        continue

                if j['body']['type'] == 'followed':
                    try:
                        await on_followed(j['body']['body'])
                    except Exception as e:
                        print(traceback.format_exc())
                        continue
                

reconnect_counter = 0

while True:
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        break
    except:
        time.sleep(10)
        reconnect_counter += 1
        print('Reconnecting...', end='')
        if reconnect_counter > 10:
            print('Too many reconnects. Exiting.')
            sys.exit(1)
        continue