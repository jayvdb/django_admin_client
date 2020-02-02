import re
import requests
from bs4 import BeautifulSoup



LOGIN_URL = "/admin/login/"
USER_URL = "/admin/auth/user/"
GROUP_URL = "/admin/auth/group/"

CSRFTOKEN_FIELD = "csrfmiddlewaretoken"


class Client:

    def __init__(self, base_url, admin_username, admin_password):
        self.base_url = base_url
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.session = requests.session()

    def expand_url(self, url, **kwargs):
        return self.base_url + url.format(**kwargs)

    def get_add_url(self, url):
        return "{}{}".format(self.expand_url(url), "add/")

    def get_change_url(self, url, id):
        return "{}{}{}".format(self.expand_url(url), id, "/change/")

    def get_delete_url(self, url, id):
        return "{}{}{}".format(self.expand_url(url), id, "/delete/")

    def get_soup(self, resp):
        return BeautifulSoup(resp.content, features="html.parser")

    def get_form(self, soup, select=None):
        forms = soup.select(select or "form")
        if len(forms) == 0:
            raise Exception("No forms!")
        if len(forms) > 1:
            print("Multiple forms!")
            for form in forms:
                print(form.prettify())
            raise Exception("Multiple forms!")
        [form] = forms
        return form

    def get_default_data(self, form):
        default_data = {}

        for elem in form.findAll("input"):
            name = elem.get("name")
            if name is None: continue

            type = elem["type"]
            if type in ["checkbox", "radio"]:
                value = "checked" in elem.attrs
            else:
                value = elem.get("value")

            default_data[name] = value

        for elem in form.findAll("select"):
            name = elem.get("name")
            if name is None: continue

            multi = "multiple" in elem.attrs

            values = []
            for option in elem.findAll("option"):
                if "selected" not in option.attrs: continue
                value = option.get("value")
                values.append(value)

            if multi:
                default_data[name] = values
            else:
                default_data[name] = values[0] if len(values) else None

        return default_data

    def encode_data(self, data):
        """Encodes data as if we were a browser POSTing a form.
        For instance, converts True/False to "on"/None, mimicking
        the standard browser behaviour for <input type="checkbox">."""
        encoded_data = {}
        for key, values in data.items():
            encoded_values = []
            if not isinstance(values, (list, tuple)):
                values = [values]
            for value in values:
                if isinstance(value, bool):
                    encoded_value = "on" if value else None
                else:
                    encoded_value = value
                encoded_values.append(encoded_value)
            encoded_data[key] = encoded_values
        return encoded_data

    def post_form(self, url, data=None, select=None):
        resp = self.session.get(url)
        soup = self.get_soup(resp)
        form = self.get_form(soup, select)

        updated_data = self.get_default_data(form)
        updated_data.update(data or {})
        encoded_data = self.encode_data(updated_data)

        resp = self.session.post(url, encoded_data)

        if resp.status_code != 200:
            raise Exception("Status wasn't 200!", resp)
        else:
            ok = True
            soup = self.get_soup(resp)
            errornotes = soup.select(".errornote")
            if errornotes:
                ok = False
                for errornote in errornotes:
                    print(errornote.prettify())
            errorlists = soup.select(".errorlist")
            if errorlists:
                ok = False
                for errorlist in errorlists:
                    print(errorlist.parent.prettify())
            if not ok:
                raise Exception("Form had errors!")

        return resp

    def login(self):
        url = self.expand_url(LOGIN_URL)
        data = {"username": self.admin_username, "password": self.admin_password}
        return self.post_form(url, data)

    def get_list_elem(self, url):
        resp = self.session.get(url)
        soup = self.get_soup(resp)
        return soup.find(attrs={"id": "result_list"})

    def get_change_regex(self, url):
        return re.compile(url + r"(?P<id>[0-9]+)" + "/change/")

    def get_change_links(self, url):
        list_elem = self.get_list_elem(self.expand_url(url))
        regex = self.get_change_regex(url)
        return list_elem.findAll(attrs={"href": regex})

    def get_ids(self, url):
        links = self.get_change_links(url)
        regex = self.get_change_regex(url)
        return [
            int(re.fullmatch(regex, link["href"]).groupdict()["id"])
            for link in links]

    def get_change_id(self, url, change_url):
        regex = self.get_change_regex(url)
        return int(re.fullmatch(regex, change_url).groupdict()["id"])

    def get_object_data(self, soup):
        form = self.get_form(soup)

        # Probably good enough...
        # We could scrub non-object fields from the default form data...
        return self.get_default_data(form)

    def get_object(self, url, id):
        change_url = self.get_change_url(url, id)
        resp = self.session.get(change_url)
        soup = self.get_soup(resp)
        return self.get_object_data(soup)

    def add_object(self, url, data):
        add_url = self.get_add_url(url)
        resp = self.post_form(add_url, data)
        return self.get_change_id(url, resp.url.replace(self.base_url, "", 1))

    def change_object(self, url, id, data):
        change_url = self.get_change_url(url, id)
        resp = self.post_form(change_url, data)
        soup = self.get_soup(resp)
        return self.get_object_data(soup)

    def delete_object(self, url, id):
        delete_url = self.get_delete_url(url, id)
        return self.post_form(delete_url)


    ###########################################################################
    # HELPER METHODS FOR SPECIFIC MODELS

    def get_users(self):
        return self.get_ids(USER_URL)

    def get_user(self, id):
        return self.get_object(USER_URL, id)

    def add_user(self, username, password):
        data = {"username": username, "password1": password, "password2": password}
        return self.add_object(USER_URL, data)

    def change_user(self, id, data):
        return self.change_object(USER_URL, id, data)

    def delete_user(self, id):
        return self.delete_object(USER_URL, id)

    def get_groups(self):
        return self.get_ids(GROUP_URL)

    def get_group(self, id):
        return self.get_object(GROUP_URL, id)
