import { Link } from "react-router-dom";
import { UserButton } from "@/auth";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Sparkles } from "lucide-react";
import { ThemeToggle } from "@/components/theme.jsx";
import AppSidebar from "@/components/app/AppSidebar";
import AssistantWidget from "@/components/app/AssistantWidget";

/**
 * The shared app shell: collapsible icon sidebar + sticky header + inset
 * content area. Everything under `[data-learnova-app]` uses the new design
 * language (index.css); the legacy brutalist styles.css is untouched.
 */
export default function AppLayout({ title, actions, children }) {
  return (
    <div data-learnova-app>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b bg-background/80 px-4 backdrop-blur">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mx-1 h-5" />
            <h1 className="text-sm font-medium">{title}</h1>
            <div className="ml-auto flex items-center gap-2">
              {actions}
              <ThemeToggle />
              <Button asChild size="sm" className="hidden sm:inline-flex">
                <Link to="/app/create">
                  <Sparkles /> Create
                </Link>
              </Button>
              <UserButton afterSignOutUrl="/" />
            </div>
          </header>
          <div className="flex-1 p-4 sm:p-6">{children}</div>
        </SidebarInset>
        <AssistantWidget />
      </SidebarProvider>
    </div>
  );
}
