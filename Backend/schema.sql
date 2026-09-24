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

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_predictions_user_id ON predictions(user_id); -- speeds up fetching all predictions made by a given user
CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id); -- speeds up fetching all posts made by a given user
CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id); -- speeds up loading all comments for a given post
CREATE INDEX IF NOT EXISTS idx_comments_user_id ON comments(user_id); -- speeds up fetching all comments made by a given user