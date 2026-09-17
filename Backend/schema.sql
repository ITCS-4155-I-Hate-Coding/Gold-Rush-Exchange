-- this is the replacement database for the mock JSON currently set up
-- this will make it easier to query and manipulate data for the backend and also to set up the id's and make sure they are
-- properly connected to each other

-- currently just the setup and design of the relationships of the database
-- will be connected to actual database soon


create table if not exists users (
    id serial primary key, -- auto incrementing id for each user
    username text not null unique, -- unique username for each user
    email text not null unique, -- will have to implement email validation either here or in the backend
    password_hash text not null, -- will use bcrypt to hash the password before storing it in the database
    created_at timestamptz not null default now() -- timestamp for when the user was created relative to UTC time
);

create table if not exists predictions (
    id serial primary key, -- auto incrementing id for each prediction
    user_id int not null references users(id) on delete cascade, -- for auto delete
    game text not null, -- the game for which the prediction is made
    prediction_text text not null, -- the actual prediction text
    
    created_at timestamptz not null default now() -- timestamp for when the prediction was created relative to UTC time
);