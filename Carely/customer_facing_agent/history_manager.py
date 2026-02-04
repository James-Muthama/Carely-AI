from datetime import datetime, timezone


class HistoryManager:
    def __init__(self, company_id, mongodb_db):
        self.company_id = company_id
        self.collection = mongodb_db.Internal_Test_Conversations
        self.history = []
        self.response_times = []
        self.start_time = datetime.now(timezone.utc)

    def load_history(self):
        """Loads last 10 exchanges."""
        doc = self.collection.find_one({"company_id": self.company_id})
        if doc and 'history' in doc:
            self.history = doc['history'][-10:]
            print(f"Loaded {len(self.history)} exchanges.")

    def add_exchange(self, question, answer, response_time):
        """Adds a new Q&A pair to memory."""
        self.history.append((question, answer))
        self.response_times.append(response_time)

        # Keep memory small
        if len(self.history) > 10:
            self.history = self.history[-10:]
            self.response_times = self.response_times[-10:]

    def save(self, session_info):
        """Saves to MongoDB with full Validator Compliance."""
        try:
            avg_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0.0
            topics = self._extract_topics()

            # Convert to list of lists for Validator
            formatted_history = [list(exchange) for exchange in self.history]

            doc = {
                "company_id": self.company_id,
                "history": formatted_history,
                "session_info": session_info,
                "conversation_metadata": {
                    "total_questions": len(self.history),
                    "average_response_time": float(avg_time),
                    "topics_discussed": topics
                },
                "updated_at": datetime.now(timezone.utc)
            }

            if not self.collection.find_one({"company_id": self.company_id}):
                doc["created_at"] = self.start_time

            self.collection.update_one(
                {"company_id": self.company_id},
                {"$set": doc},
                upsert=True
            )
        except Exception as e:
            print(f"Error saving history: {e}")

    def _extract_topics(self):
        """Simple keyword extraction."""
        topics = set()
        stop_words = {'what', 'how', 'when', 'where', 'why', 'the', 'is', 'can', 'does', 'please'}
        for q, _ in self.history:
            words = q.lower().replace('?', '').split()
            for w in words:
                clean = w.strip('.,!"')
                if len(clean) > 3 and clean not in stop_words:
                    topics.add(clean)
        return list(topics)[:10]

    def clear(self):
        self.history = []
        self.response_times = []
        self.save({})