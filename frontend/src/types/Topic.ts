
export interface Topic {
  id: string;
  title: string;
  description: string;
  difficulty: string;
  icon: string;
  prerequisites: string[];
  estimated_time: number;
  mentor_id?: string;
  created_at?: string;
  video_description?: string;
  explanation?: string;
  key_takeaway?: string;
  quiz_question?: string;
  quiz_options?: string[];
  quiz_correct_answer?: string;
}
