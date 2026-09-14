"""Read only the active Chrome document through the native Linux accessibility bus."""
import json,time

def read(pid,budget=.45):
    import gi
    gi.require_version('Atspi','2.0')
    from gi.repository import Atspi,GLib
    Atspi.set_timeout(60,60)
    deadline=time.monotonic()+budget
    desktop=Atspi.get_desktop(0)
    app=next((a for i in range(desktop.get_child_count()) if (a:=desktop.get_child_at_index(i)) and a.get_process_id()==pid),None)
    if not app: return None
    frame=next((a for i in range(app.get_child_count()) if (a:=app.get_child_at_index(i)) and a.get_state_set().contains(Atspi.StateType.ACTIVE)),None)
    if not frame: return None
    def children(a):
        return [c for i in range(min(1500,a.get_child_count())) if (c:=a.get_child_at_index(i))]
    queue=[frame]; documents=[]; visited=0
    while queue and time.monotonic()<deadline and visited<1500:
        node=queue.pop(); visited+=1
        try:
            if not node.get_state_set().contains(Atspi.StateType.SHOWING): continue
            if node.get_role()==Atspi.Role.DOCUMENT_WEB: documents.append(node)
            else: queue.extend(reversed(children(node)))
        except GLib.Error: continue
    text=[]; links=[]; length=0
    def intersects(a,b):
        return a.width>0 and a.height>0 and a.x+a.width>b.x and a.y+a.height>b.y and a.x<b.x+b.width and a.y<b.y+b.height
    for document in documents:
        bounds=document.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
        queue=[document]
        while queue and time.monotonic()<deadline and visited<3000 and length<65536:
            node=queue.pop(); visited+=1
            try:
                state=node.get_state_set(); role=node.get_role()
                if not state.contains(Atspi.StateType.SHOWING) or state.contains(Atspi.StateType.EDITABLE) or role==Atspi.Role.PASSWORD_TEXT: continue
                component=node.get_component_iface()
                if component and not intersects(component.get_extents(Atspi.CoordType.SCREEN),bounds): continue
                if role==Atspi.Role.LINK:
                    link=node.get_hyperlink()
                    if link:
                        uri=link.get_uri(0)
                        if uri and len(links)<1000: links.append(uri)
                if role in {Atspi.Role.STATIC,Atspi.Role.TEXT}:
                    value=node.get_name()[:65536-length]
                    text.append(value); length+=len(value)
                queue.extend(reversed(children(node)))
            except GLib.Error: continue
    if time.monotonic()>=deadline or visited>=3000 or length>=65536: return None
    return {'text':'\n'.join(text),'links':list(dict.fromkeys(links)),'source':'chrome accessibility'}

if __name__=='__main__':
    import sys
    try: print(json.dumps(read(int(sys.argv[1]))))
    except Exception: print('null')
