from datetime import datetime
import os

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("ESPORTS_SECRET", "ggwp-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///esports_blog.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    summary = db.Column(db.String(240), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(400))
    category = db.Column(db.String(80))
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    author = db.relationship("User", backref=db.backref("posts", lazy=True))
    comments = db.relationship(
        "Comment", backref="post", cascade="all, delete-orphan", lazy="dynamic"
    )
    feedback = db.relationship(
        "PostFeedback", backref="post", cascade="all, delete-orphan", lazy="dynamic"
    )

    def hero_image(self):
        return self.image_url or "https://images.unsplash.com/photo-1511512578047-dfb367046420?auto=format&fit=crop&w=1600&q=80"

    def helpful_votes(self):
        return self.feedback.filter_by(helpful=True).count()

    def not_helpful_votes(self):
        return self.feedback.filter_by(helpful=False).count()


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    author = db.relationship("User", backref=db.backref("comments", lazy=True))


class PostFeedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    helpful = db.Column(db.Boolean, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    __table_args__ = (
        db.UniqueConstraint("post_id", "user_id", name="unique_post_feedback"),
    )
    voter = db.relationship("User", backref=db.backref("feedback_votes", lazy=True))


def seed_demo_posts():
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(username="admin")
        admin.set_password("ggwp123!")
        db.session.add(admin)
        db.session.commit()

    if Post.query.count() > 0:
        reassigned = 0
        for post in Post.query.all():
            if post.user_id != admin.id:
                post.author = admin
                post.user_id = admin.id
                reassigned += 1
        if reassigned:
            db.session.commit()
        return

    posts = [
        Post(
            title="How T1 Dominates the Rift",
            summary="Macro play, roaming discipline, and laser-focused drafts keep Faker and crew atop the LCK.",
            content="""T1’s current streak is built on early mid-priority and synchronized jungle tracking. They lean on flexible champs for Faker, draft disengage for keria, then punish every rotation with pre-planned vision traps. The key takeaway for amateur teams: communicate lane states every wave and call timers out loud.""",
            image_url="https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=1400&q=80",
            category="MOBA",
            author=admin,
        ),
        Post(
            title="CS2 Utility Setups for Ancient",
            summary="T-side control hinges on instant cave pressure and double-molly executes over mid.",
            content="""Ancient rewards teams that deny CT aggression. Pair a fast cave pop flash with a deep donut smoke so lurkers can pinch A. Once rifles plant, keep one HE for post-plant to punish defuse taps. Practice these lineups in custom servers until muscle memory kicks in.""",
            image_url="https://images.unsplash.com/photo-1511512578047-dfb367046420?auto=format&fit=crop&w=1200&q=80",
            category="FPS",
            author=admin,
        ),
        Post(
            title="Valorant Fracture Playbook",
            summary="Double controller comps unlock brutal pincer hits—here’s the round-by-round plan.",
            content="""Use Breach to clear tower while Harbor walls off generator, letting Neon sprint into site without crossfire. On defense, anchor with Killjoy util stacked on B tower and rotate early—Fracture favors proactive swings. Review VODs to ensure your reactions line up with sound cues.""",
            image_url="https://images.unsplash.com/photo-1506111583091-d69f4b0da347?auto=format&fit=crop&w=1300&q=80",
            category="Tactics",
            author=admin,
        ),
    ]

    db.session.add_all(posts)
    db.session.commit()


@app.route("/")
def index():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    base_query = Post.query.order_by(Post.date_posted.desc())

    if category:
        base_query = base_query.filter(Post.category.ilike(category))

    if query:
        like = f"%{query}%"
        posts = base_query.filter(
            or_(Post.title.ilike(like), Post.summary.ilike(like), Post.content.ilike(like))
        ).all()
    else:
        posts = base_query.all()

    categories = (
        db.session.query(Post.category).filter(Post.category.isnot(None)).distinct().all()
    )

    featured_post = posts[0] if posts else None
    feed_posts = posts[1:] if len(posts) > 1 else []

    stats = {
        "posts": Post.query.count(),
        "comments": Comment.query.count(),
        "members": User.query.count(),
    }

    return render_template(
        "index.html",
        posts=posts,
        featured_post=featured_post,
        feed_posts=feed_posts,
        query=query,
        category=category,
        categories=[c[0] for c in categories],
        stats=stats,
    )


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("Log in to join the discussion.", "warning")
            return redirect(url_for("login", next=url_for("post_detail", post_id=post.id)))
        body = request.form.get("body", "").strip()
        if not body:
            flash("Comment cannot be empty.", "danger")
            return redirect(url_for("post_detail", post_id=post.id))
        comment = Comment(body=body, post=post, author=current_user)
        db.session.add(comment)
        db.session.commit()
        flash("Play-by-play added!", "success")
        return redirect(url_for("post_detail", post_id=post.id, _anchor="comments"))

    comments = post.comments.order_by(Comment.created_at.desc()).all()
    user_vote = None
    if current_user.is_authenticated:
        user_vote = PostFeedback.query.filter_by(
            post_id=post.id, user_id=current_user.id
        ).first()
    return render_template(
        "post.html",
        post=post,
        comments=comments,
        helpful_votes=post.helpful_votes(),
        not_helpful_votes=post.not_helpful_votes(),
        user_vote=user_vote,
    )


@app.route("/post/<int:post_id>/feedback", methods=["POST"])
@login_required
def post_feedback(post_id):
    post = Post.query.get_or_404(post_id)
    action = request.form.get("action")
    if action not in ("helpful", "not_helpful"):
        flash("Invalid feedback option.", "danger")
        return redirect(url_for("post_detail", post_id=post.id))

    helpful_flag = action == "helpful"
    feedback = PostFeedback.query.filter_by(
        post_id=post.id, user_id=current_user.id
    ).first()
    if feedback:
        feedback.helpful = helpful_flag
        message = "Feedback updated."
    else:
        feedback = PostFeedback(helpful=helpful_flag, post=post, voter=current_user)
        db.session.add(feedback)
        message = "Thanks for the feedback!"
    db.session.commit()
    flash(message, "success")
    anchor = "feedback" if helpful_flag else "feedback"
    return redirect(url_for("post_detail", post_id=post.id, _anchor=anchor))


@app.route("/profile/<string:username>")
def profile(username):
    username = username.strip().lower()
    user = User.query.filter_by(username=username).first()
    if not user:
        abort(404)

    posts = (
        Post.query.filter_by(user_id=user.id)
        .order_by(Post.date_posted.desc())
        .all()
    )
    comments = (
        Comment.query.filter_by(user_id=user.id)
        .order_by(Comment.created_at.desc())
        .limit(6)
        .all()
    )
    helpful_received = sum(post.helpful_votes() for post in posts)
    not_helpful_received = sum(post.not_helpful_votes() for post in posts)

    stats = {
        "posts": len(posts),
        "comments": Comment.query.filter_by(user_id=user.id).count(),
        "helpful": helpful_received,
        "not_helpful": not_helpful_received,
    }

    return render_template(
        "profile.html",
        user_profile=user,
        posts=posts,
        comments=comments,
        stats=stats,
    )


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_post():
    if request.method == "POST":
        post = Post(
            title=request.form["title"],
            summary=request.form["summary"],
            content=request.form["content"],
            image_url=request.form.get("image_url"),
            category=request.form.get("category"),
            author=current_user,
        )
        db.session.add(post)
        db.session.commit()
        flash("Match recap published!", "success")
        return redirect(url_for("index"))
    return render_template("add_post.html")


@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        flash("You can only edit your own recaps.", "danger")
        return redirect(url_for("post_detail", post_id=post.id))
    if request.method == "POST":
        post.title = request.form["title"]
        post.summary = request.form["summary"]
        post.content = request.form["content"]
        post.image_url = request.form.get("image_url")
        post.category = request.form.get("category")
        db.session.commit()
        flash("Post updated.", "info")
        return redirect(url_for("post_detail", post_id=post.id))
    return render_template("edit_post.html", post=post)


@app.route("/delete/<int:post_id>", methods=["POST"])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        flash("You can only delete your own posts.", "danger")
        return redirect(url_for("post_detail", post_id=post.id))
    db.session.delete(post)
    db.session.commit()
    flash("Post removed.", "warning")
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        flash("You are already logged in.", "info")
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        confirm = request.form["confirm_password"]

        if not username or not password:
            flash("Username and password required.", "danger")
            return redirect(url_for("register"))
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))
        if User.query.filter_by(username=username).first():
            flash("Handle already taken.", "warning")
            return redirect(url_for("register"))

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created! Time to queue up.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Welcome back to the arena!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("index"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))


@app.context_processor
def inject_year():
    return {"current_year": datetime.utcnow().year}


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_demo_posts()
    app.run(debug=True, port=5010)


