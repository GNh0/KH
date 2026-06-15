CREATE OR ALTER PROCEDURE [dbo].[sp_DEMO_SELECT] @WORKTYPE VARCHAR(20)=NULL, @ORGDIV VARCHAR(2)=NULL
AS
BEGIN
SET NOCOUNT ON
SELECT a.ordnum, dbo.F_BA011T_FIND_SUBNM('DE001', a.status, 'Y') AS statusnm,
       CASE WHEN a.chkyn = 'Y' THEN '확인' END AS chkynm,
       a.qty * a.price AS amt
FROM DE100T a
left outer join DE110T b
on a.ordnum = b.ordnum
and a.ordseq = b.ordseq
WHERE a.orgdiv = @ORGDIV
AND a.status = '진행'
--AND a.status = '보류'
END
