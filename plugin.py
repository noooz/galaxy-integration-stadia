import logging
import sys
import os
import pathlib
import re
import requests
from galaxy.api.plugin import Plugin, create_and_run_plugin
from galaxy.api.consts import Platform
from galaxy.api.types import Authentication, NextStep, Game, LicenseType, LicenseInfo
from galaxy.api.errors import AuthenticationRequired, InvalidCredentials

logging.getLogger().setLevel(logging.ERROR)

logger = logging.getLogger('stadia')
logger.setLevel(logging.INFO)
logger.info('start stadia plugin (test)')

class StadiaPlugin(Plugin):
    def __init__(self, reader, writer, token):
        super().__init__(Platform.Stadia, "0.1", reader, writer, token)

    # implement methods
    async def authenticate(self, stored_credentials=None):
        logger.info('authenticate')

        self._auth_cookies = stored_credentials['cookies'] if stored_credentials else None
        logger.info('auth_cookies: %s' % self._auth_cookies)  

        if self._auth_cookies:
            try:
                return self.create_user()
            except:
                logger.info('relogin')

        return NextStep("web_session", {
                "window_title": "Anmelden – Google Konten",
                "window_width": 560,
                "window_height": 610,
                "start_uri": "https://accounts.google.com/SignOutOptions?continue=https%3A%2F%2Fstadia.google.com%2F",
                "end_uri_regex": "^" + re.escape("https://stadia.google.com/home")
            })
     
    async def pass_login_credentials(self, step, credentials, cookies):
        logger.info('pass_login_credentials')
        auth_cookies = {
            c['name']:c['value'] 
            for c in cookies 
            if c['name'] in ['HSID', 'SID', 'SSID'] and c['domain'] == '.google.com'
        }
        logger.info('auth_cookies: %s' % auth_cookies)

        self.store_credentials({'cookies' : auth_cookies})
        self._auth_cookies = auth_cookies

        return self.create_user()

    def create_user(self):
        r = self.request_url('https://stadia.google.com/home')
        m = re.search('<span class="VY8blf fSorq">(.*?)</span>.*<div class="gI3hkd">(.*?)</div>', r.text)
        
        # with open(os.sep.join([str(pathlib.Path.home()), 'stadio-user.html']), 'wb') as f:
        #     f.write(r.content)

        if m:
            user = m[1]
            user_id = m[2]
        else:
            user = user_id = 'unknown'

        logger.info('user_id: %s, user: %s' % (user_id, user))

        return Authentication(user_id, user)

    def request_url(self, url):
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.97 Safari/537.36'})
        r = session.get(url, cookies=self._auth_cookies, allow_redirects=True)
        logger.info('url: %s (%s)' % (r.url, len(r.history)))
        if r.url.startswith('https://accounts.google.com/'):
        #if not r.url.startswith(url):
            logger.info('%s <=> %s' % (r.url, url))
            raise AuthenticationRequired()

        return r

    async def get_owned_games(self):
        logging.debug('getting owned games')

        logger.info('auth_cookies: %s' % self._auth_cookies)

        r = self.request_url('https://stadia.google.com/home')

        # with open(os.sep.join([str(pathlib.Path.home()), 'stadio-home.html']), 'wb') as f:
        #     f.write(r.content)

        games = [m[1] for m in re.finditer('class="GqLi4d QAAyWd qu6XL"[^>]*aria-label="(.*?)"', r.text)]
        games = [re.sub(' ansehen.$', '', g) for g in games]
        
        last_played_game = [m[1] for m in re.finditer('class="Rt8Z2e qRvogc QAAyWd" aria-label="(.*?)"', r.text)]
        last_played_game[0] = last_played_game[0].split(' Spielen')[0]
        games.append(Game(last_played_game[0], last_played_game, [], LicenseInfo(LicenseType.OtherUserLicense)))
        

        logger.info('games: %s' % games)

        games = [Game(g, g, [], LicenseInfo(LicenseType.OtherUserLicense)) for g in games]

        return games

def main():
    create_and_run_plugin(StadiaPlugin, sys.argv)

# run plugin event loop
if __name__ == "__main__":
    main()
