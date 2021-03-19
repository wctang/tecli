import os
import io
from pprint import pprint
import argparse
import sqlite3
import contextlib
import telethon
import telethon.sync
from PIL import Image

api_id = 3515943
api_hash = 'ef921033eaad45116ea326ef31dada14'

def init_db(dbfile):
    db_init = [
        'CREATE TABLE IF NOT EXISTS CHL (id INTEGER, username TEXT, title TEXT, photo BLOB)',
        'CREATE TABLE IF NOT EXISTS MSG (id INTEGER, date INTEGER, sender_id INTEGER, reply_to INTEGER, text TEXT, media TEXT, data BLOB)',
        'CREATE TABLE IF NOT EXISTS USR (id INTEGER, username TEXT, displayname TEXT, photo BLOB)',
    ]
    conn = sqlite3.connect(dbfile)
    for st in db_init:
        conn.execute(st)
    return conn


async def action_refresh_channel_message(client, id):
    channel = None
    dbfile = None
    if os.path.isfile(id):
        dbfile = id
    else:
        try:
            channel = await client.get_entity(int(id))
            if type(channel) != telethon.tl.types.Channel:
                print(f"{id} is not Channel, Exit!")
                return
            dbfile = f'{channel.title}.db'
        except ValueError:
            print(f"{id} is not Channel, Exit!")
            return

    with contextlib.closing(init_db(dbfile)) as conn:
        cid = None
        with conn:
            r = conn.execute("SELECT id,username,title,photo FROM CHL").fetchone()
            if r is None:
                if channel == None:
                    raise UserWarning()
                photo = await client.download_profile_photo(entity=channel, download_big=False, file=bytes)
                conn.execute("INSERT INTO CHL(id,username,title,photo) values (?,?,?,?)", (channel.id, channel.username, channel.title, photo))
                cid = channel.id
            else:
                cid = r[0]

        uids = []
        for row in conn.execute("SELECT id FROM USR"):
            uids.append(row[0])

        r = conn.execute("SELECT MAX(id) from MSG").fetchone()
        offset_id = r[0] if r[0] is not None else 0

        cnt = 0
        print(f"==== offset_id: {offset_id}")
        async for m in client.iter_messages(entity=cid, offset_id=offset_id, reverse=True):
            if type(m) == telethon.tl.patched.MessageService:
                continue

            if type(m) == telethon.tl.patched.Message:
                sid = m.sender_id
                if sid is None:
                    continue

                if sid < -1000000000000:
                    sid = sid * -1 -1000000000000

                entity = None
                displayname = None
                photo = None
                if sid not in uids:
                    entity = await m.get_sender()
                    try:
                        if entity.photo is not None:
                            img = await client.download_profile_photo(entity=entity, download_big=False, file=bytes)
                            img = Image.open(io.BytesIO(img))
                            img = img.resize((40, 40))
                            img_b = io.BytesIO()
                            img.save(img_b, format='JPEG')
                            photo = img_b.getvalue()
                    except:
                        pass

                    if type(entity) == telethon.tl.types.User:
                        displayname = f"{'' if entity.first_name is None else entity.first_name}{'' if entity.first_name is None or entity.last_name is None else ' '}{'' if entity.last_name is None else entity.last_name}"
                    elif type(entity) == telethon.tl.types.Channel:
                        displayname = entity.title


                media, data = await process_media(m)

                with conn:
                    conn.execute("INSERT INTO MSG(id,date,sender_id,reply_to,text,media,data) values (?,?,?,?,?,?,?)", (m.id, int(m.date.timestamp()), sid, m.reply_to.reply_to_msg_id if m.is_reply else 0, m.text, media, data))
                    if entity is not None:
                        conn.execute("INSERT INTO USR(id,username,displayname,photo) values (?,?,?,?)", (entity.id, entity.username, displayname, photo))
                        uids.append(entity.id)
                        print(f'append user {entity.id}')

                print(f"== ({m.id}) {m.date}")

                cnt += 1
                if cnt > 1000:
                    conn.commit()


async def process_media(m):
    media = m.media
    if media is None:
        return '', None
    media_t = type(media)

    if media_t == telethon.tl.types.MessageMediaDocument:
        pre = "file"
        alt = ""
        fn = ""
        for att in media.document.attributes:
            if type(att) == telethon.tl.types.DocumentAttributeSticker:
                pre = "sticker"
                alt = att.alt
            elif type(att) == telethon.tl.types.DocumentAttributeFilename:
                fn = att.file_name
        return f"{pre}\t{alt}\t{media.document.mime_type}\t{fn}", None

    elif media_t == telethon.tl.types.MessageMediaPhoto:
        # dir = f'{workdir}/media/{(m.id % 100):02}'
        # os.makedirs(dir, exist_ok=True)
        # fn = f"{dir}/pic_{m.id}_1.jpg"
        data = await m.download_media(file=bytes, thumb=1)
        return f"pic", data

    elif media_t == telethon.tl.types.MessageMediaWebPage:
        webpage = media.webpage
        if type(webpage) == telethon.tl.types.WebPage:
            return f"url\t{webpage.url}\t{webpage.site_name}\t{webpage.title}", None
        elif type(webpage) == telethon.tl.types.WebPageEmpty:
            return '', None

    elif media_t == telethon.tl.types.MessageMediaContact:
        return f"telethon.tl.types.MessageMediaContact", None

    elif media_t == telethon.tl.types.MessageMediaPoll:
        return f"telethon.tl.types.MessageMediaPoll", None

    elif media_t == telethon.tl.types.MessageMediaDice:
        return f"telethon.tl.types.MessageMediaDice", None

    else:
        print(f"{media_t}", media, m)
        raise UserWarning()


async def action_list_all_dialog(client):
    # # client.
    # ent = await client.get_entity(676179719)
    # print(type(ent))
    # print(ent.to_dict())
    # return

    async for dialog in client.iter_dialogs():
        if isinstance(dialog.entity, telethon.tl.types.Channel):
            chl = dialog.entity
            print("CHL:", chl.id, chl.title, chl.username)
        elif isinstance(dialog.entity, telethon.tl.types.User):
            usr = dialog.entity
            print("USR:", usr.id, usr.first_name, usr.last_name, usr.username)


def main():
    parser = argparse.ArgumentParser(description='tecli')
    parser.add_argument("id", type=str, nargs='?', help="id or file")
    args = parser.parse_args()

    with telethon.sync.TelegramClient('tecli', api_id, api_hash) as client:
        if args.id is None:
            client.loop.run_until_complete(action_list_all_dialog(client))
        else:
            client.loop.run_until_complete(action_refresh_channel_message(client, args.id))


if __name__ == "__main__":
    main()
