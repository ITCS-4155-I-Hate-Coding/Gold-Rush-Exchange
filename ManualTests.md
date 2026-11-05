**Make sure to run 'python apply_schema.py' to make sure that the database shchema and tables are up to date**
**To test with User A and User B, use a regular tab and in incognito tab to simulate using two different users**

1. Signing Up and Login Rules (==🟡Make sure to write down the login info to go into specific users and test features later==)
   1. Try registering with username 'ab', password 'abc', and gmail address
      1. do each of these separately to test individual errors
   2. Register properly to make sure it goes through
   3. Try logging into the properly registered account with the strong password
      1. wrong password should say "Invalid email or password"
2. Making a Prediction
   1. On predictions tab, click predict on a game, pick a team and wager 50
      1. rep should drop by 50 points
      2. The game tile should show your pick and should not show Predict button anymore
      3. In My Picks, it should show as 'Pending' with 50 rep points at stake
      4. A wager larger than ones balance should be refused
3. Posting and Community Rep
   1. post something 15+ characters long, then post 'hi', and make a couple more real posts
      1. the first post should get 5 points
      2. the 'hi' post should show but should not receive any points
      3. the 4th post made that day should not give any points since 3 is the limit for posts
4. Photos
   1. Add a photo to a post (try to pick a real photo between 2-5MB or less than 64KB)
   2. Have another user or teammate open Posts on their computer
      1. Should see a preview of the picture before posting it
      2. the photo should show up in the feed and clicking the photo opens it to full size
      3. should show up on other user or teammates computer (checking database works)
      4. A file over 5MB is refused (pdfs should not work as well)
      5. Allows gifs, webp, jpeg, png
5. Likes, dislikes, and rep
   1. User B likes A's post, unlikes it, likes it again, then switches it to a dislike
      1. User A should gain 1+ rep once through all of this
      2. Switching to a dislike should move the count from likes to dislikes and User A rep should not change
      3. Liking your own post should earn nothing
6. Comments
   1. User B comments on A's post; User A comments on their own post
      1. User B should get +2 rep
      2. A's comment should not earn any rep
7. Notifications
   1. after making a first post look at the bell icon at the top
      1. the bell should show a 1 and opening it should show "Achievement unlocked: First Words"
      2. clicking the notification opens your profile on Achievements
      3. "Mark all read" button should clear the count of the notifications
8. Featured badges
   1. go to Profile -> Achievements -> Earned and click Show on a badge. Then try to show more than 3 badges
      1. the badge should fill a slot and appear next to your name in the header of your profile and posts
      2. trying to add a 4th badge should give an "up to 3" message
9. Friends and messages
   1. User A follows User B, but User B doesnt follow back
   2. User B follows User A back
   3. User A sends a message
      1. After step one, there should be no message button available since the relationship is just one way (since User B didnt follow back)
      2. After User B follows back, a Message button should appear
      3. User B should see a red 1 on messages and opening that chat should remove the red 1
      4. User B reply shows up for A without refreshing the page
10. Unfollowing
    1. User B unfollows User A
       1. A can still read old messages, but the message box is replaced by a note saying that they cannot send messages
11. Profile tabs and lists
    1. on your Profile, try the Won/Lost/Refunded filters, check the "Show more" button, check activity tab
       1. Each of the filters count should match its rows
       2. "Show 8 more" should show that many more rows
       3. The Activity tab should show posts, comments, and picks from targeted user
       4. Someones elses profiles should show a Follow button and no Empty badge slots
12. Leaderboard
    1. open Leaderboard, switch to Achievements, then to Following
       1. The top 3 appear on the podium with 1st place in the middle and your row should be slightly highlighted
       2. Achievements re-ranks everyone by their achievement score rather than reputation points
       3. Following shows only people you follow
       4. Two players with the same rep share a rank number
13. Following tab
    1. click picks on someone, then "See all their picks", then show more
       1. Picks should show their open picks and the last 5 settled ones
       2. "See all their picks" opens their profile
       3. Show more should load more activity
14. Homepage
    1. While logged out, choose a team and a wager in Up next, then click the gold button
    2. Log in, repeat, and click Make this pick
       1. Up next lists real upcoming games
       2. Choosing a team and wager shows win/lise amounts, and the button opens the login
       3. When logged in, the prediction form opens with the same team and wager filled in
15. About page
    1. click each button logged out and logged in and open each FAQ question
       1. Each button opens its tab
       2. Messages, Compare, and My Achievements open the login when your logged out
       3. FAQ answers should expand
