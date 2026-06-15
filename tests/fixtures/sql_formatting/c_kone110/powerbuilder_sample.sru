forward
global type n_cst_demo from nonvisualobject
end type
end forward

public function integer of_save ()
string ls_sql

ls_sql = "UPDATE DE100T SET STATUS = '진행' WHERE ORDNUM = :AS_ORDNUM";

SELECT DE100T.ORDNUM,
       DE100T.STATUS
INTO :ls_ordnum,
     :ls_status
FROM DE100T
WHERE DE100T.STATUS = '진행';

return 1
end function
