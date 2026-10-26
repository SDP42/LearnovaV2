import { DecksIllustration } from "@/components/app/Illustrations";
import { Button } from "@/components/ui/button";

export default function DashEmpty({ onSample }) {
  return (
    <div className="lv-r-hero flex flex-col items-center gap-3 border border-dashed border-[#DCC6B4] bg-white/70 px-6 py-10 text-center">
      <DecksIllustration />
      <h2 className="t-h2">Your first deck is one paragraph away</h2>
      <p className="t-body max-w-md text-muted-foreground">
        Describe a topic or drop a PDF above. Learnova turns it into slides, visuals and quizzes in about a minute.
      </p>
      <Button onClick={onSample} variant="outline" className="mt-1">
        Try with a sample syllabus
      </Button>
    </div>
  );
}
