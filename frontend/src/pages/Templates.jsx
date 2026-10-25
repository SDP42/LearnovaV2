import { useSearchParams } from "react-router-dom";
import AppLayout, { EmbeddedCtx } from "@/components/app/AppLayout";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageContainer, PageHeader } from "@/components/app/Page";
import Gallery from "@/pages/Gallery";
import Library from "@/pages/Library";

/** Templates = Library (ready-made lessons) + Gallery (community topics) as tabs. */
export default function Templates() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "community" ? "community" : "lessons";
  return (
    <AppLayout title="Templates">
      <PageContainer>
        <PageHeader title="Templates" subtitle="Start from a ready-made lesson or a community topic. One click fills the composer." />
        <Tabs value={tab} onValueChange={(v) => setParams(v === "lessons" ? {} : { tab: v }, { replace: true })}>
          <TabsList className="h-10 rounded-full bg-[#E3ECF9] p-1">
            <TabsTrigger value="lessons" className="rounded-full px-4 data-[state=active]:text-[#1D4ED8]">Lessons</TabsTrigger>
            <TabsTrigger value="community" className="rounded-full px-4 data-[state=active]:text-[#1D4ED8]">Community gallery</TabsTrigger>
          </TabsList>
          <EmbeddedCtx.Provider value={true}>
            <TabsContent value="lessons" className="mt-5"><Library /></TabsContent>
            <TabsContent value="community" className="mt-5"><Gallery /></TabsContent>
          </EmbeddedCtx.Provider>
        </Tabs>
      </PageContainer>
    </AppLayout>
  );
}
