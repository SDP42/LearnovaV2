import { Link, useLocation } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  BrainCircuit,
  FolderKanban,
  LayoutDashboard,
  Library,
  Presentation,
  Settings,
  Sparkles,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

const GROUPS = [
  {
    label: "Workspace",
    items: [
      { title: "Dashboard", to: "/app", icon: LayoutDashboard },
      { title: "Create", to: "/app/create", icon: Sparkles },
      { title: "Projects", to: "/app/projects", icon: FolderKanban },
    ],
  },
  {
    label: "Learning",
    items: [
      { title: "Presentations", to: "/app/presentations", icon: Presentation },
      { title: "Quizzes", to: "/app/quizzes", icon: BrainCircuit },
      { title: "Analytics", to: "/app/analytics", icon: BarChart3 },
    ],
  },
  {
    label: "Resources",
    items: [
      { title: "Library", to: "/app/library", icon: Library },
      { title: "Docs", to: "/app/docs", icon: BookOpen },
    ],
  },
];

export default function AppSidebar() {
  const { pathname } = useLocation();
  const isActive = (to) =>
    to === "/app" ? pathname === "/app" : pathname.startsWith(to);

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <Link
          to="/app"
          className="flex items-center gap-2 rounded-md px-2 py-1.5 group-data-[collapsible=icon]:justify-center"
        >
          <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Sparkles className="size-4" />
          </div>
          <span className="text-base font-semibold tracking-tight group-data-[collapsible=icon]:hidden">
            Learnova
          </span>
        </Link>
      </SidebarHeader>

      <SidebarContent>
        {GROUPS.map((group) => (
          <SidebarGroup key={group.label}>
            <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
            <SidebarMenu>
              {group.items.map((item) => (
                <SidebarMenuItem key={item.to}>
                  <SidebarMenuButton
                    asChild
                    isActive={isActive(item.to)}
                    tooltip={item.title}
                  >
                    <Link to={item.to}>
                      <item.icon />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild isActive={isActive("/app/settings")} tooltip="Settings">
              <Link to="/app/settings">
                <Settings />
                <span>Settings</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
