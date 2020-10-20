import os
from flask import Flask, render_template, request, session, redirect
from devops import DevOps, Project
from dotenv import load_dotenv


load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if "token" in session:
            session.pop("token")

        return render_template("login.html")

    if request.method == "POST":
        token = request.form.get("token")
        if not token:
            return render_template("login.html", errors=["Invalid/Missing Token."])

        session["token"] = token
        return redirect("/")


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/project/existing", methods=["GET", "POST"])
def existing_projects():
    if "token" not in session:
        return redirect("/login")

    if request.method == "GET":
        return render_template("project/existing_project.html")

    if request.method == "POST":
        org_name = request.form.get("org_name")
        if not org_name:
            return render_template(
                "project/existing_project.html",
                errors=["Invalid/Missing Organization Name"],
            )

        try:
            d = DevOps(personal_access_token=session["token"], org_name=org_name)
            projects_dict = d.get_existing_projects()
        except Exception as err:
            errors = [
                "Failed to get data from Azure DevOps; check token and organization name."
            ]
            errors += list(err.args)
            return render_template("project/existing_project.html", errors=errors,)

        if not projects_dict:
            return render_template("project/existing_project.html", projects=[])

        return render_template("project/existing_project.html", projects=projects_dict)


if __name__ == "__main__":
    app.run(debug=True)
