
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
  explanation?: string;
  key_takeaway?: string;
}
