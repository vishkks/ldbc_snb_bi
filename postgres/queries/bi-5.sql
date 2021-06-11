/* Q5. Most active posters in a given topic
\set tag '\'Abbas_I_of_Persia\''
 */
WITH detail AS (
SELECT CreatorPerson.id AS CreatorPersonId
     , count(DISTINCT Comment.Id)  AS replyCount
     , count(DISTINCT Person_likes_Message.MessageId||' '||Person_likes_Message.PersonId) AS likeCount
     , count(DISTINCT Message.Id)  AS messageCount
     , NULL as score
  FROM Message_hasTag_Tag
  JOIN Message
    ON Message.id = Message_hasTag_Tag.MessageId
  LEFT JOIN Comment
         ON Message.id = coalesce(Comment.ParentPostId, Comment.ParentCommentId)
  LEFT JOIN Person_likes_Message
         ON Message.id = Person_likes_Message.MessageId
  JOIN Person CreatorPerson
    ON CreatorPerson.id = Message.CreatorPersonId
  JOIN Tag
    ON Tag.id = Message_hasTag_Tag.TagId
   AND Tag.name = :tag
 GROUP BY CreatorPerson.id
)
SELECT CreatorPersonId AS "person.id"
     , replyCount
     , likeCount
     , messageCount
     , 1*messageCount + 2*replyCount + 10*likeCount AS score
  FROM detail
 ORDER BY score DESC, CreatorPersonId
 LIMIT 100
;
