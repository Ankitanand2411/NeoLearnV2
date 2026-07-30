export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  public: {
    Tables: {
      profiles: {
        Row: {
          avatar: string | null
          avatar_url: string | null
          created_at: string
          full_name: string | null
          id: string
          updated_at: string
          user_id: string
          username: string | null
        }
        Insert: {
          avatar?: string | null
          avatar_url?: string | null
          created_at?: string
          full_name?: string | null
          id?: string
          updated_at?: string
          user_id: string
          username?: string | null
        }
        Update: {
          avatar?: string | null
          avatar_url?: string | null
          created_at?: string
          full_name?: string | null
          id?: string
          updated_at?: string
          user_id?: string
          username?: string | null
        }
        Relationships: []
      }
      quiz_sessions: {
        Row: {
          completed_at: string | null
          created_at: string
          id: string
          questions_data: Json
          score: number | null
          topic_id: string
          user_answers: Json | null
          user_id: string
        }
        Insert: {
          completed_at?: string | null
          created_at?: string
          id?: string
          questions_data: Json
          score?: number | null
          topic_id: string
          user_answers?: Json | null
          user_id: string
        }
        Update: {
          completed_at?: string | null
          created_at?: string
          id?: string
          questions_data?: Json
          score?: number | null
          topic_id?: string
          user_answers?: Json | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "quiz_sessions_topic_id_fkey"
            columns: ["topic_id"]
            isOneToOne: false
            referencedRelation: "topics"
            referencedColumns: ["id"]
          },
        ]
      }
      topics: {
        Row: {
          created_at: string
          description: string | null
          difficulty: string | null
          explanation: string | null
          icon: string | null
          id: string
          key_takeaway: string | null
          prerequisites: string[] | null
          quiz_correct_answer: string | null
          quiz_options: string[] | null
          quiz_question: string | null
          title: string
          video_description: string | null
        }
        Insert: {
          created_at?: string
          description?: string | null
          difficulty?: string | null
          explanation?: string | null
          icon?: string | null
          id?: string
          key_takeaway?: string | null
          prerequisites?: string[] | null
          quiz_correct_answer?: string | null
          quiz_options?: string[] | null
          quiz_question?: string | null
          title: string
          video_description?: string | null
        }
        Update: {
          created_at?: string
          description?: string | null
          difficulty?: string | null
          explanation?: string | null
          icon?: string | null
          id?: string
          key_takeaway?: string | null
          prerequisites?: string[] | null
          quiz_correct_answer?: string | null
          quiz_options?: string[] | null
          quiz_question?: string | null
          title?: string
          video_description?: string | null
        }
        Relationships: []
      }
      user_badges: {
        Row: {
          badge_name: string
          earned_at: string
          id: string
          user_id: string
        }
        Insert: {
          badge_name: string
          earned_at?: string
          id?: string
          user_id: string
        }
        Update: {
          badge_name?: string
          earned_at?: string
          id?: string
          user_id?: string
        }
        Relationships: []
      }
      user_mastery: {
        Row: {
          created_at: string
          id: string
          last_attempted_at: string
          mastery_level: number
          questions_attempted: number
          questions_correct: number
          topic_id: string
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          last_attempted_at?: string
          mastery_level?: number
          questions_attempted?: number
          questions_correct?: number
          topic_id: string
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          id?: string
          last_attempted_at?: string
          mastery_level?: number
          questions_attempted?: number
          questions_correct?: number
          topic_id?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "user_mastery_topic_id_fkey"
            columns: ["topic_id"]
            isOneToOne: false
            referencedRelation: "topics"
            referencedColumns: ["id"]
          },
        ]
      }
      user_progress: {
        Row: {
          completed_at: string
          id: string
          topic_id: string
          user_id: string
        }
        Insert: {
          completed_at?: string
          id?: string
          topic_id: string
          user_id: string
        }
        Update: {
          completed_at?: string
          id?: string
          topic_id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "user_progress_topic_id_fkey"
            columns: ["topic_id"]
            isOneToOne: false
            referencedRelation: "topics"
            referencedColumns: ["id"]
          },
        ]
      }
      user_streaks: {
        Row: {
          created_at: string
          current_streak: number
          id: string
          last_activity_date: string | null
          longest_streak: number
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          current_streak?: number
          id?: string
          last_activity_date?: string | null
          longest_streak?: number
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          current_streak?: number
          id?: string
          last_activity_date?: string | null
          longest_streak?: number
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      leaderboard_top5: {
        Row: {
          avatar: string | null
          avg_mastery: number | null
          user_id: string | null
          username: string | null
        }
        Relationships: []
      }
    }
    Functions: {
      update_mastery_level: {
        Args: { user_uuid: string; topic_uuid: string; is_correct: boolean }
        Returns: number
      }
      update_user_streak: {
        Args: { user_uuid: string }
        Returns: undefined
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DefaultSchema = Database[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof Database },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof Database
  }
    ? keyof (Database[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        Database[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends { schema: keyof Database }
  ? (Database[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      Database[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof Database },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof Database
  }
    ? keyof Database[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends { schema: keyof Database }
  ? Database[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof Database },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof Database
  }
    ? keyof Database[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends { schema: keyof Database }
  ? Database[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof Database },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof Database
  }
    ? keyof Database[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends { schema: keyof Database }
  ? Database[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof Database },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof Database
  }
    ? keyof Database[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends { schema: keyof Database }
  ? Database[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
