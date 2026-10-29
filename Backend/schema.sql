-- this is the replacement database for the mock JSON currently set up
-- this will make it easier to query and manipulate data for the backend and also to set up the id's and make sure they are
-- properly connected to each other

-- currently just the setup and design of the relationships of the database
-- will be connected to actual database soon




-- Users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY, -- auto incrementing id for each user
    username TEXT NOT NULL UNIQUE, -- unique username for each user
    email TEXT NOT NULL UNIQUE, -- will have to implement email validation in the backend
    password_hash VARCHAR(60) NOT NULL, -- will use bcrypt to hash the password before storing it in the database
    reputation INT NOT NULL DEFAULT 1000, -- default reputation for new users
    created_at TIMESTAMPTZ NOT NULL DEFAULT now() -- timestamp for when the user was created relative to UTC time
);

-- Predictions
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY, -- auto incrementing id for each prediction
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- for auto delete
    game TEXT NOT NULL, -- the game for which the prediction is made like "Duke vs UNC"
    prediction_text TEXT NOT NULL, -- the actual prediction text so "Duke will win"
    points INT NOT NULL CHECK (points > 0), -- the number of points the user is betting on this prediction, must be greater than 0
    result TEXT NOT NULL DEFAULT 'pending' CHECK (result in ('pending', 'correct', 'incorrect')), -- the result of the prediction, can be 'pending', 'correct', or 'incorrect'

    created_at TIMESTAMPTZ NOT NULL DEFAULT now() -- timestamp for when the prediction was created relative to UTC time
);


-- Posts
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY, -- auto incrementing id for each post
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- for auto delete
    content TEXT NOT NULL, -- the content of the post
    likes INTEGER NOT NULL DEFAULT 0, -- the number of likes for the post
    created_at TIMESTAMPTZ NOT NULL DEFAULT now() -- timestamp for when the post was created relative to UTC time
);

-- Comments
CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY, -- auto incrementing id for each comment
    post_id INT NOT NULL REFERENCES posts(id) ON DELETE CASCADE, -- for auto delete
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- for auto delete
    content TEXT NOT NULL, -- the content of the comment
    likes INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now() -- timestamp for when the comment was created relative to UTC time
);

-- Post likes (tracks which user liked which post so a second click unlikes instead of double-counting)
CREATE TABLE IF NOT EXISTS post_likes (
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id INT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, post_id)
);

-- Comment likes (same idea as post_likes)
CREATE TABLE IF NOT EXISTS comment_likes (
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    comment_id INT NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, comment_id)
);


-- Table to allow games to show in the future and update from ESPN
CREATE TABLE IF NOT EXISTS games (
    id SERIAL PRIMARY KEY, 
    external_id TEXT NOT NULL UNIQUE, -- the ESPN event id
    sport TEXT NOT NULL CHECK (sport IN ('football', 'basketball')),
    home_team TEXT NOT NULL, 
    away_team TEXT NOT NULL, 
    start_time TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'in_progress', 'final')),
    home_score INT,
    away_score INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- table alterations for future additions to schema, app, and backend sections

ALTER TABLE predictions ADD COLUMN IF NOT EXISTS game_id INT REFERENCES games(id) ON DELETE CASCADE;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS pick TEXT CHECK (pick IN ('home', 'away'));

-- rankings (AP Top 25, NULL = unranked) and conferences for filtering games
ALTER TABLE games ADD COLUMN IF NOT EXISTS home_rank INT;
ALTER TABLE games ADD COLUMN IF NOT EXISTS away_rank INT;
ALTER TABLE games ADD COLUMN IF NOT EXISTS home_conference TEXT;
ALTER TABLE games ADD COLUMN IF NOT EXISTS away_conference TEXT;

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_predictions_user_id ON predictions(user_id); -- speeds up fetching all predictions made by a given user
CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id); -- speeds up fetching all posts made by a given user
CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id); -- speeds up loading all comments for a given post
CREATE INDEX IF NOT EXISTS idx_comments_user_id ON comments(user_id); -- speeds up fetching all comments made by a given user
CREATE INDEX IF NOT EXISTS idx_games_sport_start ON games(sport, start_time);


-- Follows (who follows who; a user can't follow themselves or follow the same person twice)
CREATE TABLE IF NOT EXISTS follows (
    follower_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    followed_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (follower_id, followed_id),
    CHECK (follower_id <> followed_id)
);
CREATE INDEX IF NOT EXISTS idx_follows_followed_id ON follows(followed_id);


-- Achievements (for gamification; users can earn achievements for various actions)
-- achievements table is the list of everything that can be earned
-- user_achievements table is the list of which users have earned which achievements
-- will come from the catalog of achievements in AchievementsBackend.py
CREATE TABLE IF NOT EXISTS achievements (
    code TEXT PRIMARY KEY, -- unique for each achievement
    track TEXT NOT NULL, -- category of achievement like "predictions", "posts", "comments", "follows"
    name TEXT NOT NULL, -- achievement name
    description TEXT NOT NULL, -- achievement description
    tier TEXT NOT NULL CHECK (tier IN ('bronze', 'silver', 'gold', 'platinum', 'diamond')),
    value INT NOT NULL CHECK (value > 0), -- achievement score this is worth
    threshold INT NOT NULL, -- number of actions required to earn this achievement
    sort_order INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- which user earned which achievements
-- using a key to make sure that the user cannot earn the same achievement twice
-- adding on delete cascade so that if a user is deleted, their achievements are also deleted
CREATE TABLE IF NOT EXISTS user_achievements (
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code TEXT NOT NULL REFERENCES achievements(code) ON DELETE CASCADE,
    earned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    featured BOOLEAN NOT NULL DEFAULT false, -- shown next to user name and we will haev a max of 3 badges showing for the time being
    seen BOOLEAN NOT NULL DEFAULT false, -- shows the achievement as locked until they earn it
    PRIMARY KEY (user_id, code)
);

-- indexing
CREATE INDEX IF NOT EXISTS idx_user_achievements_code ON user_achievements(code);
CREATE INDEX IF NOT EXISTS idx_user_achievements_featured ON user_achievements(user_id) WHERE featured;


-- Fix for games that are cancelled
-- Wagers on these games will be refunded
ALTER TABLE games DROP CONSTRAINT IF EXISTS games_status_check;
ALTER TABLE games ADD CONSTRAINT games_status_check CHECK (status IN ('scheduled', 'in_progress', 'final', 'canceled'));

ALTER TABLE predictions DROP CONSTRAINT IF EXISTS predictions_result_check;
ALTER TABLE predictions ADD CONSTRAINT predictions_result_check CHECK (result IN ('pending', 'correct', 'incorrect', 'void'));
CREATE INDEX IF NOT EXISTS idx_predictions_game_id ON predictions(game_id); -- settlement joins on this


-- Fixing to one prediction per game because before the page would hide the Predict
