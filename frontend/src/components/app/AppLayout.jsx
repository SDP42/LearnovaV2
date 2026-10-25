import { createContext, useContext } from "react";
import { createPortal } from "react-dom";

/** Provided by AppShell: DOM slots in the persistent header. */
export const ShellCtx = createContext(null);
/** Set by pages that embed another page inside tabs (renders children only). */
export const EmbeddedCtx = createContext(false);

/**
 * Per-page wrapper. The persistent chrome (sidebar, 48px header, command
 * palette, route transitions) lives in AppShell; a page just declares its
 * header title/actions and gets the 1200px / 24px-gutter content column.
 */
export default function AppLayout({ title, actions, children }) {
  const slots = useContext(ShellCtx);
  const embedded = useContext(EmbeddedCtx);
  if (embedded) return <>{children}</>;
  return (
    <>
      {slots?.title ? createPortal(title, slots.title) : null}
      {slots?.actions && actions ? createPortal(actions, slots.actions) : null}
      <div className="lv-page">{children}</div>
    </>
  );
}
