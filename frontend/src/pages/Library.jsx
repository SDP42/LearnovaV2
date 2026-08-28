import { useNavigate } from "react-router-dom";
import { ArrowRight, BookOpen, FlaskConical, LineChart, Workflow } from "lucide-react";
import AppLayout from "@/components/app/AppLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

/**
 * Starter templates — click one to open Create pre-filled. Kept in the client
 * so it works offline; the backend already accepts typed input.
 */
const TEMPLATES = [
  {
    icon: Workflow,
    title: "Process / workflow",
    hint: "Ordered steps → flowchart + progressive reveal",
    topic: "The Machine Learning Workflow",
    text: `## The Machine Learning Workflow
1. Frame the problem and collect a labelled dataset
2. Split the data into training, validation and test sets
3. Choose a model family and a loss function
4. Train the model and tune hyperparameters on the validation set
5. Evaluate on the held-out test set
6. If performance is poor, gather more data or change the model, then repeat

## Common Pitfalls
- Data leakage between the training and test sets
- Optimising the model on the test set instead of the validation set
- Ignoring class imbalance in the evaluation metric`,
  },
  {
    icon: LineChart,
    title: "Concept with data",
    hint: "Numbers over categories → bar / pie",
    topic: "Renewable Energy Mix",
    text: `## Global Electricity by Source
Coal supplies 36% of world electricity, natural gas 23%, hydro 15%, nuclear 10%, wind 7%, solar 5% and other renewables 4%.

## Advantages and Drawbacks of Wind
- An advantage is that wind is free and inexhaustible
- A benefit is zero direct emissions while operating
- A drawback is that output is intermittent
- A limitation is the visual and noise impact on nearby communities`,
  },
  {
    icon: FlaskConical,
    title: "Definitions & theory",
    hint: "Precise wording → kept verbatim",
    topic: "Thermodynamics Basics",
    text: `## Key Definitions
Entropy is defined as a measure of the number of microscopic configurations that correspond to a thermodynamic system's macroscopic state.
The first law states that energy cannot be created or destroyed, only transferred or converted.
The second law states that the total entropy of an isolated system can never decrease over time.

## Heat Engines
A heat engine converts thermal energy into mechanical work by exploiting a temperature difference between a hot and a cold reservoir.`,
  },
];

export default function Library() {
  const navigate = useNavigate();

  return (
    <AppLayout title="Library">
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Starter templates</h2>
          <p className="text-sm text-muted-foreground">
            Each opens the Create screen pre-filled so you can see how the engine
            handles a different kind of content.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          {TEMPLATES.map((t) => (
            <Card key={t.title} className="lv-card flex flex-col p-5">
              <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <t.icon className="size-5" />
              </span>
              <h3 className="mt-3 font-medium">{t.title}</h3>
              <p className="mt-1 flex-1 text-sm text-muted-foreground">{t.hint}</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-4 self-start"
                onClick={() =>
                  navigate("/app/create", { state: { template: { topic: t.topic, text: t.text } } })
                }
              >
                Use template <ArrowRight />
              </Button>
            </Card>
          ))}
        </div>

        <Card className="lv-card">
          <CardContent className="flex items-start gap-3 p-5">
            <BookOpen className="mt-0.5 size-5 shrink-0 text-primary" />
            <div>
              <p className="font-medium">Design & research docs</p>
              <p className="mt-1 text-sm text-muted-foreground">
                The visual taxonomy, the PSF engagement metric, and the Deck
                Director design all live in <code>docs/research/</code> in the
                repository.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
