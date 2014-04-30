# -*- coding: utf-8 -*-
#
# This file is part of Lalf.
#
# Lalf is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Foobar is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Lalf.  If not, see <http://www.gnu.org/licenses/>.

import logging
logger = logging.getLogger("lalf")

import re
from pyquery import PyQuery
import time
import os

from lalf.util import month, clean_filename
from lalf.user import User
from lalf import ocr
from lalf import ui
from lalf import session

class OcrUser(User):
    STATE_KEEP = ["id", "newid", "name", "mail", "posts", "date", "lastvisit", "trust", "img"]

    def __init__(self, parent, id, newid, name, posts, date):
        """
        id -- id of the user in the old forum
        newid -- id of the user in the new forum
        name -- username
        mail -- email address
        posts -- number of posts
        date -- subscription date (timestamp)
        lastvisit -- date of last visit (timestamp)
        trust -- level of trust in the email (3 if we are sure that
          the email is correct, 2 if it is probable, 1 if it is not, 0 if
          none was found)
        img -- path of the image containing the email
        """
        User.__init__(self, parent, id, newid, name, None, posts, date, 0, incuser=False)
        self.trust = 0
        self.img = os.path.join("usermails", "{username}.png".format(username=clean_filename(self.name)))

    def validate_email(self):
        """
        Validate the email address found by checking that searching for
        the users who have the address self.mail returns the user
        self.name.
        """
        params = {
            "part" : "users_groups",
            "sub" : "users",
            "username" : self.mail,
            "submituser" : "Ok",
            "sort" : "user_id",
            "order" : "ASC"
        }
        r = session.get_admin("/admin/index.forum", params=params)
        
        d = PyQuery(r.text)

        for i in d('tbody tr'):
            e = PyQuery(i)

            if e("td a").eq(0).text() == self.name:
                return True

        return False
        
    def _export_(self, inc=True):
        logger.debug('Récupération du membre %d', self.id)
        
        if inc:
            self.inc()
        
        # Search for users with name self.name
        try:
            encodedname = self.name.encode("latin1")
        except:
            encodedname = self.name
        
        params = {
            "part" : "users_groups",
            "sub" : "users",
            "username" : encodedname,
            "submituser" : "Ok",
            "sort" : "user_id",
            "order" : "ASC"
        }
        r = session.get_admin("/admin/index.forum", params=params)

        d = PyQuery(r.text)

        for i in d('tbody tr'):
            e = PyQuery(i)
            if e("td a").eq(0).text() == self.name:
                # The user was found
                self.mail = e("td a").eq(1).text()
                if self.mail == "" and e("td a").eq(0).is_('img'):
                    # The administration panel has been blocked, the
                    # email is replaced by an image, get it
                    r = session.get(e("td a img").eq(0).attr("src"))
                    with open(self.img, "wb") as f:
                        f.write(r.content)

                    # Pass it through the OCR
                    self.mail = ocr.totext(self.img)
                    if ocr.toolong(self.img):
                        # The image is too small for the email, the
                        # user will have to give it
                        self.trust = 1
                    elif self.validate_email():
                        self.trust = 3
                    else:
                        self.trust = 2
                else:
                    # The administration panel hasn't been blocked
                    # yet, the email is available
                    self.mail 
                    self.trust = 3

                lastvisit = e("td").eq(4).text()
            
                if lastvisit != "":
                    lastvisit = lastvisit.split(" ")
                    self.lastvisit = time.mktime(time.struct_time((int(lastvisit[2]),month(lastvisit[1]),int(lastvisit[0]),0,0,0,0,0,0)))
                else:
                    self.lastvisit = 0
        
    def confirm_email(self, r=2):
        if self.trust == 2:
            logger.info("L'adresse email de l'utilisateur {name} est probablement valide mais n'a pas pu être validée.".format(name=self.name))
            print("Veuillez saisir l'adresse email de l'utilisateur {name} (laissez vide si l'adresse {email} est correcte) :".format(name=self.name, email=self.mail))
            self.mail = input("> ").strip()
        elif self.trust == 1:
            logger.info("L'adresse email de l'utilisateur {name} est probablement invalide.".format(name=self.name))
            print("Veuillez saisir l'adresse email de l'utilisateur {name} (laissez vide si l'adresse {email} est correcte) :".format(name=self.name, email=self.mail))
            self.mail = input("> ").strip()
        elif self.trust == 0:
            logger.info("L'adresse email de l'utilisateur {name} n'a pas pu être exportée.".format(name=self.name))
            if r == 0:
                print("Veuillez saisir l'adresse email de l'utilisateur {name} :".format(name=self.name))
                self.mail = input("> ").strip()
            else:
                self._export_(False)
                self.confirm_email(r-1)