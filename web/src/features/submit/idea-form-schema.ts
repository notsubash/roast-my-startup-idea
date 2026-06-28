import { z } from "zod";

export const ideaFormSchema = z.object({
  idea: z
    .string()
    .trim()
    .min(10, "At least 10 characters — give the judges something to work with.")
    .max(8000, "Keep it under 8,000 characters."),
  target_customer: z.string().optional(),
  pricing: z.string().optional(),
  traction: z.string().optional(),
  competitorsText: z.string().optional(),
  model_runtime: z.enum(["local", "deepseek"]),
  max_debate_rounds: z.number().int().min(1).max(5),
  enable_web_search: z.boolean(),
});

export type IdeaFormValues = z.infer<typeof ideaFormSchema>;

export const ideaFormDefaults: IdeaFormValues = {
  idea: "",
  target_customer: "",
  pricing: "",
  traction: "",
  competitorsText: "",
  model_runtime: "deepseek",
  max_debate_rounds: 3,
  enable_web_search: false,
};

export const IDEA_MAX_LENGTH = 8000;
