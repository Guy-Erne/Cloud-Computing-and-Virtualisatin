#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# importing webapp2 framework for google app engine
import webapp2
# importing jinja 2 for template rendering
import jinja2
# importing os to get current director
import os
# importing users to get google login emulation
from google.appengine.api import users
# importing ndb for querying datastore
from google.appengine.ext import ndb
# importing blobstore_handler for upload blog files in this case image
from google.appengine.ext.webapp import blobstore_handlers
# importing blobstore for blog key
from google.appengine.ext import blobstore
# importing json to dump json string in case of ajax requests
import json
# importing datetime for post/comment creation
import datetime

# jinja template environment with autoescape html entities
jinja = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True
)


# following model
# used in structured property in Account model
class Following(ndb.Model):
    follower = ndb.KeyProperty()  # key of user who follows another user
    following = ndb.KeyProperty()  # key of another user who has been followed


# Accounts model for logged in users
class Account(ndb.Model):
    email = ndb.StringProperty()  # email as StringProperty
    follower = ndb.StructuredProperty(Following,
                                      repeated=True)  # follower as structured property to hold list of this user's followers
    following = ndb.StructuredProperty(Following,
                                       repeated=True)  # following as structured property to hold list of user's whom this user is following
    created = ndb.DateTimeProperty(auto_now=True)  # creation date of user


# Comment model used as structured property in posts
class Comment(ndb.Model):
    user = ndb.KeyProperty()  # key of user who comments
    post = ndb.KeyProperty()  # post where the comment is posted on
    comment = ndb.TextProperty()  # comment text
    created = ndb.DateTimeProperty(auto_now=True)  # comment created date


class Post(ndb.Model):
    user = ndb.KeyProperty()  # key of user who created post
    image = ndb.BlobKeyProperty()  # image in post
    caption = ndb.TextProperty()  # caption of post
    comments = ndb.StructuredProperty(Comment, repeated=True)  # comments the post has
    created = ndb.DateTimeProperty()  # created date of comment


class BaseHandler(webapp2.RequestHandler):
    # default variables for all classes

    # dictionary to pass template variables into view
    template_values = {}
    # upload user to handle blob files
    upload_url = ""
    # user object as Account Model
    user_object = None

    def __init__(self, request, response):
        super(BaseHandler, self).__init__(request=request, response=response)
        self.user = users.get_current_user()

        if self.user:
            url = users.create_logout_url(self.request.uri)
            self.user_object = Account.query(Account.email == users.get_current_user().email()).get()
            # if not in datastore insert in datastore and get object
            if not self.user_object:
                # creating user object with Account model and storing in datastore
                self.user_object = Account(email=users.get_current_user().email())
                self.user_object.put()
            #     creating upload url
            self.upload_url = blobstore.create_upload_url('/post/save')
            # assigning upload url to template variable as view parameters
            self.template_values["upload_url"] = self.upload_url
        else:
            # creating login url incase user is not logged in
            url = users.create_login_url(self.request.uri)
            # redirecting to login url after user is found not to be logged in
            self.redirect(url)
        # adding user object in view parameters
        self.template_values["user"] = self.user_object
        # adding log in / out url
        self.template_values["log_url"] = url


class FollowHandler(BaseHandler):
    def __init__(self, request, response):
        # constructor
        # calling parent class constructor to initialize variables
        super(FollowHandler, self).__init__(request, response)

    # onclick of follow button
    def post(self):
        # getting user id who is to be followed
        following_user_id = self.request.get("follow_user_id")
        # creating key of user who is to be followed
        following_user = ndb.Key(Account, int(following_user_id))
        # following_user is followed by follower_user
        # which is current logged in user
        follower_user = ndb.Key(Account, int(self.user_object.key.id()))

        # creating following model object to use it as structured property on user
        following = Following(following=following_user, follower=follower_user)
        # cheking if same object is already in user's following
        already_followed = Account.query(Account.following == following).fetch()
        # following user if not followed and button action is to follow
        if self.request.get('follow') == "Follow" and not already_followed:
            # get user to be followed from key
            following_user = following_user.get()
            # get user who is following from key
            follower_user = follower_user.get()
            # append in follower property of following user
            following_user.follower.append(following)
            # append in following property of follower user
            follower_user.following.append(following)
            # updating follower user
            follower_user.put()
            # updating following user
            following_user.put()
        # if button action is unfollow and the pair is already followed
        elif self.request.get('follow') == "Unfollow" and already_followed:
            # get follower user
            follower_user = Account.query(Account.following == following).get()
            # get following user
            following_user = Account.query(Account.follower == following).get()
            # remove the follower's data
            following_user.follower.remove(following)
            # update user
            following_user.put()
            # remove following users data
            follower_user.following.remove(following)
            # update user
            follower_user.put()
        self.redirect('/profile/' + following_user_id)


# feed page handler
class MainHandler(BaseHandler):
    def __init__(self, request, response):
        super(MainHandler, self).__init__(request, response)

    def get(self):
        if self.user:
            # get following users as list
            following = map(lambda account: account.following, self.user_object.following)
            # adding current user(ownself) to following user list; as user should see his own post in feed
            following.append(self.user_object.key)
            # query post data store with descending order by created date and limiting to 50 records
            posts = Post.query(Post.user.IN(following)).order(-Post.created).fetch(limit=50)
            # passing posts variable to template values as view parameter
            self.template_values['posts'] = posts
            # rendering template with view parameters
            self.response.write(jinja.get_template("index.html").render(self.template_values))


# Class to download uploaded images
class ImageHandler(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, img_id):
        if self.user:
            # get post key
            post_key = ndb.Key(urlsafe=img_id)
            # getting post from key
            post = post_key.get()
            # post has image field as blog key

            if not blobstore.get(post.image):
                self.error(404)
            else:
                # getting blog from blogkey and sending response as image
                self.send_blob(post.image)

# user profile handler
class ProfileHandler(BaseHandler):
    def __init__(self, request, response):
        super(ProfileHandler, self).__init__(request, response)

    def get(self, user_id):
        if self.user:
            # get user profile
            profile_user = Account.get_by_id(int(user_id))
            # check if profile is current user's profile
            my_profile = self.user_object.key.id() == profile_user.key.id()
            # check if profile is already followed by current usr
            following = Following(following=profile_user.key, follower=self.user_object.key)
            already_followed = Account.query(Account.following == following).fetch()
            # get posts created by this profile user
            posts = Post.query(Post.user == profile_user.key).order(-Post.created).fetch()
            # pass view parameters
            self.template_values['posts'] = posts
            self.template_values['profile_user'] = profile_user
            self.template_values['my_profile'] = my_profile
            self.template_values['followed'] = already_followed
            # render template
            self.response.write(jinja.get_template("profile.html").render(self.template_values))

# send response on key press in search input
class SearchHandler(BaseHandler):
    def __init__(self, request, response):
        super(SearchHandler, self).__init__(request, response)

    def get(self):
        if self.user:
            # getting data in request sent as q
            query = self.request.get('q').strip()
            # initialising searched users container
            account_dict = []
            if len(query):
                # get all emails where string is greater than given string in input
                accounts = Account.query(Account.email >= query).fetch()
                # create account dictionary
                # map each account to return id and email of user.
                account_dict = map(lambda account: {"id": account.key.id(), "email": account.email}, accounts)
            # send response as json string
            self.response.write(json.dumps(account_dict))


class PostHandler(blobstore_handlers.BlobstoreUploadHandler):
    template_values = {}
    base_url = ""
    upload_url = ""
    user_object = None

    def __init__(self, request, response):
        super(PostHandler, self).__init__(request, response)

        self.user = users.get_current_user()

        if self.user:
            url = users.create_logout_url(self.request.uri)
            self.user_object = Account.query(Account.email == users.get_current_user().email()).get()
            # if not in datastore insert in datastore and get object
            if not self.user_object:
                # creating user object with Account model and storing in datastore
                self.user_object = Account(email=users.get_current_user().email())
                self.user_object.put()
            self.upload_url = blobstore.create_upload_url('/post/save')
            self.template_values["upload_url"] = self.upload_url
        else:
            url = users.create_login_url(self.request.uri)
            self.redirect(url)

        self.template_values["user"] = self.user_object
        self.template_values["log_url"] = url

    def get(self, post_id):
        if self.user:
            # get post's id
            post = Post.get_by_id(int(post_id))
            # get profile user from post
            profile_user = post.user.get()
            # check if post/profile is of current user
            my_profile = self.user_object.key.id() == profile_user.key.id()
            # check if is already followed
            following = Following(following=profile_user.key, follower=self.user_object.key)
            already_followed = Account.query(Account.following == following).fetch()
            # assign view parameters
            self.template_values['post'] = post
            self.template_values['profile_user'] = profile_user
            self.template_values['my_profile'] = my_profile
            self.template_values['followed'] = already_followed
            # render post.html with view parameters
            self.response.write(jinja.get_template("post.html").render(self.template_values))

    def post(self):
        if self.user:
            # uploading image
            upload = self.get_uploads()[0]
            # getting file info i.e fileanme, size etc
            file_info = blobstore.BlobInfo(upload.key())
            filename = file_info.filename
            # getting extension from file
            if file_info.filename.split('.')[1] in ['png', 'jpg', 'jpeg']:
                # processing only if extension is jpg or png
                # storing post in datastore with current time
                post = Post(
                    user=Account.query(Account.email == users.get_current_user().email()).get().key,
                    caption=self.request.get('caption'),
                    image=upload.key(),
                    created=datetime.datetime.now()
                )
                # saving post
                post.put()
            #     redirecting to feed page
            self.redirect('/')

# showing followers and following list
class FollowersHandler(BaseHandler):
    def __init__(self, request, response):
        super(FollowersHandler, self).__init__(request, response)

    def get(self, user_id):
        if self.user:
            # get user whose followers/followings are checked
            profile_user = Account.get_by_id(int(user_id))
            # check if this is current user's profile
            my_profile = self.user_object.key.id() == profile_user.key.id()
            # check if already followed
            following = Following(following=profile_user.key, follower=self.user_object.key)
            already_followed = Account.query(Account.following == following).fetch()

            self.template_values['profile_user'] = profile_user
            self.template_values['my_profile'] = my_profile
            self.template_values['followed'] = already_followed
            # mapping profile users follower from strucutred property "follower" to get id and email of user in list
            followers = map(lambda account: {"id": account.follower.id(), "email": account.follower.get().email},
                            profile_user.follower)
            # assinging followers list to view
            self.template_values['users_list'] = followers
            self.template_values['users_list_title'] = "Followed by"
            # rendering view
            self.response.write(jinja.get_template("userlist.html").render(self.template_values))


class FollowingHandler(BaseHandler):
    def __init__(self, request, response):
        super(FollowingHandler, self).__init__(request, response)

    def get(self, user_id):
        if self.user:
            # getting profile user
            profile_user = Account.get_by_id(int(user_id))
            # chcking if this is current users profile
            my_profile = self.user_object.key.id() == profile_user.key.id()
            # checing if already followed
            following = Following(following=profile_user.key, follower=self.user_object.key)
            already_followed = Account.query(Account.following == following).fetch()
            # passing view parameters
            self.template_values['profile_user'] = profile_user
            self.template_values['my_profile'] = my_profile
            self.template_values['followed'] = already_followed
            # mapping profile users following users from structured property to get id and email
            following_accounts = map(
                lambda account: {"id": account.following.id(), "email": account.following.get().email},
                profile_user.following)
            # assigning following accounts into list
            self.template_values['users_list'] = following_accounts
            self.template_values['users_list_title'] = "Following"
            self.response.write(jinja.get_template("userlist.html").render(self.template_values))

# comments on post handler
class CommentHandler(BaseHandler):

    def __init__(self, request, response):
        super(CommentHandler, self).__init__(request, response)

    def post(self):
        if self.user:
            # getting post id
            post_id = self.request.get("post_id").strip()
            # getting comment
            comment = self.request.get("comment").strip()
            # getting post from id
            post = Post.get_by_id(int(post_id))
            # truncating comment if length greater than 200
            comment = comment[:75] if len(comment) > 200 else comment
            if comment and post and self.user_object:
                # inserting comment if everything goes good
                # inserting comment into post's comment structured property
                post.comments.insert(0, Comment(user=self.user_object.key, post=post.key, comment=comment))
                post.put()
            self.redirect("/")


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/post/save', PostHandler),
    (r'/image/(.+)', ImageHandler),
    (r'/profile/(\d+)', ProfileHandler),
    (r'/profile/(\d+)/followers', FollowersHandler),
    (r'/profile/(\d+)/following', FollowingHandler),
    (r'/follow', FollowHandler),
    (r'/search', SearchHandler),
    (r'/comment', CommentHandler),
    (r'/post/(\d+)', PostHandler),
], debug=True)
