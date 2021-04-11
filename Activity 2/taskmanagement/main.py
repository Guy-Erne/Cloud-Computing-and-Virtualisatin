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

# import all libraries
import webapp2
import jinja2
import os
from google.appengine.api import users
from google.appengine.ext import ndb
# datetime library required to compute task completion date
import datetime

# jinja template environment with autoescape html entities
jinja = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True
)


# handler for /
# home page handler
class MainHandler(webapp2.RequestHandler):
    def get(self):
        # initialize user object and user's taskboard
        user_object = None
        my_taskboards = None
        # if user is logged in then show taskboards dashboard
        if users.get_current_user():
            # get user object if user is in datastore
            user_object = User.query(User.email == users.get_current_user().email()).get()
            # if not in datastore insert in datastore and get object
            if not user_object:
                # creating user object with User model and storing in datastore
                user_object = User(email=users.get_current_user().email())
                user_object.put()

            # get all taskboards created by user
            my_taskboards = Taskboard.query(Taskboard.creator == user_object.key).fetch()
            # get all taskboards user is invited into
            invited_taskboards = TaskboardUser.query(TaskboardUser.user == user_object.key).fetch()
            # merge taskboards i.e created by user and where user is invited into
            for invited_taskboard in invited_taskboards:
                # appending into my_taskboards list
                my_taskboards.append(invited_taskboard.taskboard.get())

        template_vars = {
            # login logout url
            # url is login if user is not currently logged in else is url for user to logout
            "url": users.create_logout_url("/") if users.get_current_user() else users.create_login_url("/"),
            # current user object
            "user": users.get_current_user(),
            # current user object from our datastore
            "user_object": user_object,
            # user's invited and created taskboards
            "taskboards": my_taskboards
        }
        # rendering home page template from main.html
        self.response.write(jinja.get_template("main.html").render(template_vars))


# Taskboard model with attributes title to hold taskboard title and creator key attribute to hold creator user's key
class Taskboard(ndb.Model):
    title = ndb.StringProperty()
    creator = ndb.KeyProperty()


# User model , holds user object after user is logged in. new object is created if datastore doesn't have the email logged in with
class User(ndb.Model):
    email = ndb.StringProperty()


# taskboard and user realtion model.
# one taskboard can have multiple user and one user can be invited into multiple taskboards.
# for many to many relation ship, attributes hold taskboard's key and user's key
class TaskboardUser(ndb.Model):
    taskboard = ndb.KeyProperty()
    user = ndb.KeyProperty()


# Task model
# one to many relation ship from taskboard to task. i.e one taskboard can have many tasks. but one task can have only one taskboard
# so creating taskboard key
class Task(ndb.Model):
    # association with taskboard
    taskboard = ndb.KeyProperty()
    # title of task
    title = ndb.StringProperty()
    # due date for task
    due_date = ndb.DateTimeProperty()
    # user key of user the task is assigned to
    assigned_user = ndb.KeyProperty()
    # flag representing task completion
    completed = ndb.BooleanProperty()
    # task completed date if complete
    completed_date = ndb.DateTimeProperty()


# Add taskboard handler
# /addtb
class AddTBHandler(webapp2.RequestHandler):
    # for displaying add taskboard form
    def get(self):
        # default template variables for view
        template_vars = {
            "url": users.create_logout_url("/") if users.get_current_user() else users.create_login_url("/"),
            "user": users.get_current_user(),
        }
        # if user is logged in then show adding form else show link for login
        if users.get_current_user():
            self.response.write(jinja.get_template("addtb.html").render(template_vars))
        else:
            # showing login link
            self.response.write("Please <a href=\"" + users.create_login_url() + "\">Login</a> to continue")

    # for saving taskboard from the form
    def post(self):
        # initialising user object
        user_object = None
        # checking if user is logged in
        if users.get_current_user():
            # getting user object from datastore if exists
            user_object = User.query(User.email == users.get_current_user().email()).get()
            # if user doesn't exist in datastore, add to datastore.
            if not user_object:
                # creating user object
                user_object = User(email=users.get_current_user().email())
                # dding to datastore.
                user_object.put()
        # if user object is successfully created, create a taskboard object and save it to datastore
        if user_object:
            # creating datasotre object
            taskboard = Taskboard(title=self.request.get("title"), creator=user_object.key)
            # saving object
            taskboard.put()
            # redirecting to home page
            self.redirect('/')
        else:
            # else showing login message
            self.response.write("Please <a href=\"" + users.create_login_url() + "\">Login</a> to continue")


# edit taskboard handler
# /edittb
class EditTBHandler(webapp2.RequestHandler):
    def get(self):
        # minimal template variables for view
        template_vars = {
            "url": users.create_logout_url("/") if users.get_current_user() else users.create_login_url("/"),
            "user": users.get_current_user(),
            "my_tb": ndb.Key(Taskboard, int(self.request.get("id"))).get()
        }
        # check if user is logged in
        if users.get_current_user():
            # get key of the taskboard provided the id in url
            key = ndb.Key(Taskboard, int(self.request.get('id')))
            user_object = User.query(User.email == users.get_current_user().email()).get()
            # if user object not in datastore, create and add in datastore
            if not user_object:
                # creating user object
                user_object = User(email=users.get_current_user().email())
                # adding in datastore
                user_object.put()
            # taskboard can be edited only if editor is the creator
            if key.get().creator == user_object.key:
                self.response.write(jinja.get_template("edittb.html").render(template_vars))
            else:
                # show unauthorised access message
                self.response.write('Unauthorised access!')
        else:
            # showing link for signing in
            self.response.write("Please <a href=\"" + users.create_login_url() + "\">Login</a> to continue")

    # for updating taskboard from editing form
    def post(self):
        user_object = None
        if users.get_current_user():
            user_object = User.query(User.email == users.get_current_user().email()).get()
            if not user_object:
                user_object = User(email=users.get_current_user().email())
                user_object.put()
            # creating taskboard object
            taskboard = ndb.Key(Taskboard, int(self.request.get('id'))).get()
            # assigning new title
            taskboard.title = self.request.get('title')
            # only creator of taskboard can update
            if taskboard.key.get().creator == user_object.key:
                taskboard.put()
            else:
                # show unauthorised access message
                self.response.write('Unauthorised access!')
            # redirect to home page after updating
            self.redirect('/')
        else:
            # show login link for user those aren't logged in
            self.response.write("Please <a href=\"" + users.create_login_url() + "\">Login</a> to continue")


class ViewTBHandler(webapp2.RequestHandler):
    def get(self):
        # if not logged in, send login message
        if users.get_current_user():
            # if logged in get user object from datastore
            user_object = User.query(User.email == users.get_current_user().email()).get()
            # if user object not in datastore, create add in datastore
            if not user_object:
                user_object = User(email=users.get_current_user().email())
                user_object.put()

            # to check if user can add task to taskboard.
            # get all users' created taskboard
            my_taskboards = Taskboard.query(Taskboard.creator == user_object.key).fetch()
            # and get all taskboard where user is invited
            invited_taskboards = TaskboardUser.query(TaskboardUser.user == user_object.key).fetch()
            # merge invited taskboards and create taskboards
            for invited_taskboard in invited_taskboards:
                my_taskboards.append(invited_taskboard.taskboard.get())

            my_tb = ndb.Key(Taskboard, int(self.request.get('id'))).get()

            # if current taskboard is in users authorised board then proceed
            if my_tb in my_taskboards:
                tb_tasks = Task.query(Task.taskboard == my_tb.key).fetch()
                template_vars = {
                    "url": users.create_logout_url("/") if users.get_current_user() else users.create_login_url("/"),
                    "user": users.get_current_user(),
                    "my_tb": my_tb,
                    "my_tb_creator": my_tb.creator.get(),
                    "tb_tasks": tb_tasks
                }

                self.response.write(jinja.get_template('viewtb.html').render(template_vars))
            else:
                self.response.write("Unauthorised access!!")
        else:
            self.response.write("Please <a href=\"" + users.create_login_url() + "\">Login</a> to continue")


class DeleteTBHandler(webapp2.RequestHandler):
    def get(self):
        if users.get_current_user():
            key = ndb.Key(Taskboard, int(self.request.get('id')))
            user_object = User.query(User.email == users.get_current_user().email()).get()
            # if user object not in datastore, create add in datastore
            if not user_object:
                user_object = User(email=users.get_current_user().email())
                user_object.put()
            #     only creator of taskboard can delete taskboard
            if key.get().creator == user_object.key:
                # creator can delete if and only if taskboard doesn't contain any tasks and any invited users.
                # i.e taskboard should not be referenced by any user for task

                # get  tasks of taskboard, and users invited to taskboard.

                if not Task.query(Task.taskboard == key).get() and not TaskboardUser.query(
                        TaskboardUser.taskboard == key).get():
                    # if no tasks and no users, perform delete
                    key.delete()
                #     redirect to home page
                self.redirect('/')
            else:
                # show unathorised access message if user is not creator of taskboard
                self.response.write('Unauthorised Access')

        else:
            # show login message for user's not logged in
            self.response.write("Please <a href=\"" + users.create_login_url() + "\">Login</a> to continue")


# add other user to this taskboard
class InviteToTBHandler(webapp2.RequestHandler):
    # show invitation form and invited users table
    def get(self):
        # only if logged in
        if users.get_current_user():
            # get users object
            user_object = User.query(User.email == users.get_current_user().email()).get()
            # if no user in  datastore add in datastore
            if not user_object:
                user_object = User(email=users.get_current_user().email())
                user_object.put()
            #     get taskbaord from key
            taskboard = ndb.Key(Taskboard, int(self.request.get('id'))).get()
            # invitation and remvoeing users from board only can be performed by creator
            if user_object.key == taskboard.creator:
                # if user pressed uninvite button
                if self.request.get('task') == 'uninvite':
                    # getting user for which uninvite button is clicked
                    uninvite_user = ndb.Key(User, int(self.request.get('uid')))
                    # get taskboard user from TaskboardUser datastore.
                    tbu = TaskboardUser.query(
                        TaskboardUser.taskboard == taskboard.key,
                        TaskboardUser.user == uninvite_user
                    ).get()
                    # if exists
                    if tbu:
                        # get all tasks user is added in this taskboard and unassign him from all tasks
                        tasks = Task.query(Task.assigned_user == uninvite_user).filter(
                            Task.taskboard == taskboard.key).fetch()
                        for task in tasks:
                            # unassigning user from every associated task in particular taskboard
                            task.assigned_user = None
                            task.put()
                        # now safely performing after removing all associations to tasks in taskboard
                        tbu.key.delete()

                invited_users_tb = TaskboardUser.query(TaskboardUser.taskboard == taskboard.key).fetch()
                # getting all already invited users to show in invite users page.
                invited_users = map(lambda invited_user: invited_user.user.get(), invited_users_tb)

                template_vars = {
                    "url": users.create_logout_url("/") if users.get_current_user() else users.create_login_url("/"),
                    "user": users.get_current_user(),
                    "user_object": user_object,
                    # all users in the system, to add them to taskboard
                    "my_users": User.query(User.key != user_object.key).fetch(),
                    "invited_users": invited_users,
                    "my_tb": taskboard
                }
                # rendering template
                self.response.write(jinja.get_template('invite.html').render(template_vars))
            else:
                # showing unauthorised access if user is not creator of taskboard
                self.response.write("Unauthorised access!")
        else:
            self.response.write("Please <a href=\"" + users.create_login_url() + "\">Login</a> to continue")

    # add users to taskboard from taskbaord form
    def post(self):
        # get taskboard
        taskboard = ndb.Key(Taskboard, int(self.request.get('tbid')))
        # if user is logged in proceed else show login link to allow user to login
        if users.get_current_user():
            # create user object
            user_object = User.query(User.email == users.get_current_user().email()).get()
            # if not user object in datastore then add into daatastore
            if not user_object:
                user_object = User(email=users.get_current_user().email())
                user_object.put()
            # taskboard to add user into
            my_tb = ndb.Key(Taskboard, int(self.request.get("tbid"))).get()
            # only if currently user is the creator of taskboard
            if my_tb.creator == user_object.key:
                # now authorised to invite

                # get all users selected from the form
                selected_users = self.request.get_all('users')
                # for each selected user, check if association to same taskboard is made previously
                for selected_user in selected_users:
                    selected_user = ndb.Key(User, int(selected_user))
                    tb_user = TaskboardUser.query(TaskboardUser.taskboard == taskboard,
                                                  TaskboardUser.user == selected_user).fetch()
                    # if association is not already made, it is safe to make now.
                    if not tb_user:
                        # making association
                        TaskboardUser(taskboard=taskboard, user=selected_user).put()
                self.redirect("/invite?id=" + self.request.get('tbid'))
            else:
                # not authorised to invite
                # get users selected
                self.response.write("Unauthorised access!")
                pass

        else:
            # showing login link for not logged in user.
            self.response.write("Please <a href=\"" + users.create_login_url() + "\">Login</a> to continue")


class AddTaskToTBHandler(webapp2.RequestHandler):
    def get(self):
        # get taskboard to add task in
        taskboard = ndb.Key(Taskboard, int(self.request.get('tbid')))
        # if not logged in, send login message
        if users.get_current_user():
            # if logged in get user object from datastore
            user_object = User.query(User.email == users.get_current_user().email()).get()
            # if user object not in datastore, create add in datastore
            if not user_object:
                user_object = User(email=users.get_current_user().email())
                user_object.put()
            # default template vars
            template_vars = {
                "url": users.create_logout_url("/") if users.get_current_user() else users.create_login_url("/"),
                "user": users.get_current_user(),
                "user_object": user_object,
                "my_tb": taskboard.get()
            }
            # to check if user can add task to taskboard.
            # get all users' created taskboard
            my_taskboards = Taskboard.query(Taskboard.creator == user_object.key).fetch()
            # and get all taskboard where user is invited
            invited_taskboards = TaskboardUser.query(TaskboardUser.user == user_object.key).fetch()
            # merge invited taskboards and create taskboards
            for invited_taskboard in invited_taskboards:
                my_taskboards.append(invited_taskboard.taskboard.get())

            # if current taskboard is in users authorised board then proceed
            if taskboard.get() in my_taskboards:
                # get all users in taskboard
                invited_users_records = TaskboardUser.query(TaskboardUser.taskboard == taskboard).fetch()
                tb_users = map(lambda invited_user: invited_user.user.get(), invited_users_records)
                template_vars["tb_users"] = tb_users
                template_vars["task"] = Task.get_by_id(int(self.request.get('tid'))) if self.request.get(
                    'job') == 'edittask' and len(self.request.get('tid')) else Task()
                self.response.write(jinja.get_template("taskform.html").render(template_vars))
            else:
                self.response.write("Unauthorised access!!")
        else:
            self.response.write("Please <a href=\"" + users.create_login_url() + "\">Login</a> to continue")

    def post(self):
        # get taskboard
        taskboard = ndb.Key(Taskboard, int(self.request.get('id')))
        # check user logged in
        if users.get_current_user():
            # if user logged in get the user
            user_object = User.query(User.email == users.get_current_user().email()).get()
            # if not found in user data store, store the user
            if not user_object:
                user_object = User(email=users.get_current_user().email())
                user_object.put()

            # check if user can add task to taskboard.
            # get all taskboards created by user
            my_taskboards = Taskboard.query(Taskboard.creator == user_object.key).fetch()
            # get all taskboards created for the user
            invited_taskboards = TaskboardUser.query(TaskboardUser.user == user_object.key).fetch()
            # merge both taskboards, as user can add for taskboards that he created and where he is invited
            for invited_taskboard in invited_taskboards:
                # merging here
                my_taskboards.append(invited_taskboard.taskboard.get())

            # if current taskboard is in users board list just merged.
            if taskboard.get() in my_taskboards:
                # processing is authenticated.
                if self.request.get('submit') == "Save Task":
                    # for new task operation
                    # again check if task with same title already exists or not.
                    # safe to add only if doesn't exists
                    if not Task.query(Task.title == self.request.get('title').strip()).get():
                        Task(
                            taskboard=ndb.Key(Taskboard, int(self.request.get('id'))),
                            title=self.request.get('title').strip(),
                            due_date=datetime.datetime.strptime(self.request.get('due_date'), '%Y-%m-%d') if len(
                                self.request.get('due_date').strip()) else None,
                            assigned_user=ndb.Key(User, int(self.request.get('uid')))
                            if len(self.request.get('uid').strip())
                            else None,
                            completed=False
                        ).put()
                elif self.request.get('submit') == "Update Task":
                    # old task edit operation
                    # again check if task with same title already exists or not.
                    # safe to add only if doesn't exists
                    if not Task.query(Task.title == self.request.get('title').strip()).filter(
                            Task.key != ndb.Key(Task, int(self.request.get("tid")))).get():
                        # get task with tid and update
                        Task(
                            id=int(self.request.get("tid")),
                            taskboard=ndb.Key(Taskboard, int(self.request.get('id'))),
                            title=self.request.get('title').strip(),
                            completed=self.request.get('completed') and self.request.get('completed').strip() == '1',
                            due_date=datetime.datetime.strptime(self.request.get('due_date'), '%Y-%m-%d'),
                            assigned_user=ndb.Key(User, int(self.request.get('uid'))) if len(
                                self.request.get('uid').strip()) else None,
                            completed_date=datetime.datetime.now() if self.request.get(
                                'completed') and self.request.get(
                                'completed').strip() == '1' else None
                        ).put()
                elif self.request.get('submit') == "Delete Task":
                    # delete the task
                    ndb.Key(Task, int(self.request.get('tid'))).delete()

                # redirect to view task link
                self.redirect('/viewtb?id=' + self.request.get('id').strip())
            else:
                # unauthorised access message
                self.response.write("Unauthorised access!!")
        else:
            # show login link to facilitate user to login
            self.response.write("Please <a href=\"" + users.create_login_url() + "\">Login</a> to continue")


# all routes
app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/addtb', AddTBHandler),
    ('/viewtb', ViewTBHandler),
    ('/edittb', EditTBHandler),
    ('/deletetb', DeleteTBHandler),
    ('/invite', InviteToTBHandler),
    ('/addtask', AddTaskToTBHandler)
], debug=True)
