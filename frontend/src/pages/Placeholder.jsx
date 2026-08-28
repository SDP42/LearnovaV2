import { Construction } from "lucide-react";
import AppLayout from "@/components/app/AppLayout";
import { Card, CardContent } from "@/components/ui/card";

/** Temporary stub for app routes not yet migrated to the new shell. */
export default function Placeholder({ title }) {
  return (
    <AppLayout title={title}>
      <div className="mx-auto max-w-2xl">
        <Card>
          <CardContent className="flex flex-col items-center gap-3 p-12 text-center">
            <Construction className="size-8 text-muted-foreground" />
            <p className="font-medium">{title}</p>
            <p className="text-sm text-muted-foreground">
              This screen is being rebuilt in the new design system.
            </p>
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
