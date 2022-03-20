// Q17. Information propagation analysis
/*
:param [{ tag, delta }] => {
  RETURN
    'Slavoj_Žižek' AS tag,
    4 AS delta
  }
*/
MATCH
  (tag:Tag {name: $tag}),
  (person1:Person)<-[:HAS_CREATOR]-(message1:Message)-[:REPLY_OF*0..]->(post1:Post)<-[:CONTAINER_OF]-(forum1:Forum),
  (message1)-[:HAS_TAG]->(tag),
  (forum1)<-[:HAS_MEMBER]->(person2:Person)<-[:HAS_CREATOR]-(comment:Comment)-[:HAS_TAG]->(tag)
// The query allows message2 = post2. If this is the case, their HAS_TAG edges to tag overlap,
// and Cypher's edge-isomorphic matching does causes does not allow for such a match in a single MATCH clause.
// To work around it, we start a new MATCH clause.
MATCH
  (forum1)<-[:HAS_MEMBER]->(person3:Person)<-[:HAS_CREATOR]-(message2:Message)-[:HAS_TAG]->(tag),
  (comment)-[:REPLY_OF]->(message2)-[:REPLY_OF*0..]->(post2:Post)<-[:CONTAINER_OF]-(forum2:Forum)
WHERE forum1 <> forum2
  AND message2.creationDate > message1.creationDate + duration({hours: $delta})
  AND NOT (forum2)-[:HAS_MEMBER]->(person1)
RETURN person1.id, count(DISTINCT message2) AS messageCount
ORDER BY messageCount DESC, person1.id ASC
LIMIT 10
